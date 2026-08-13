import os
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings

GITHUB_URL_PATTERN = re.compile(r"^/([^/]+)/([^/]+)/?$")


def _win_path(path: Path) -> Path:
    """Format path with Windows extended-length prefix (\\?\\) to bypass MAX_PATH 260-char limit."""
    if os.name == "nt":
        abs_str = str(path.resolve())
        if not abs_str.startswith("\\\\?\\"):
            return Path("\\\\?\\" + abs_str)
    return path


@dataclass(frozen=True)
class GitHubRepositoryData:
    owner: str
    name: str
    full_name: str
    html_url: str
    description: str | None
    owner_avatar_url: str | None
    stars_count: int
    forks_count: int
    primary_language: str | None
    languages: dict[str, int]
    default_branch: str
    size_kb: int


def parse_github_repository_url(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a public https://github.com/owner/repository URL.")
    match = GITHUB_URL_PATTERN.fullmatch(parsed.path.rstrip("/"))
    if not match or parsed.query or parsed.fragment:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a repository root URL without a branch, path, query, or fragment.")
    owner, repository = match.groups()
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not owner or not repository:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid GitHub repository URL.")
    return owner, repository


class GitHubClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10", "User-Agent": "github-mentor-ai"}
        if settings.github_token:
            self.headers["Authorization"] = f"Bearer {settings.github_token}"

    async def get_repository(self, owner: str, name: str) -> GitHubRepositoryData:
        async with httpx.AsyncClient(base_url="https://api.github.com", headers=self.headers, timeout=30.0, follow_redirects=True) as client:
            repository_response = await client.get(f"/repos/{owner}/{name}")
            self._raise_for_github_error(repository_response, owner, name)
            repository = repository_response.json()
            if repository.get("private", False):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only public repositories can be imported.")
            languages_response = await client.get(f"/repos/{owner}/{name}/languages")
            self._raise_for_github_error(languages_response, owner, name)
        return GitHubRepositoryData(
            owner=repository["owner"]["login"], name=repository["name"], full_name=repository["full_name"], html_url=repository["html_url"],
            description=repository.get("description"), owner_avatar_url=repository["owner"].get("avatar_url"), stars_count=repository.get("stargazers_count", 0),
            forks_count=repository.get("forks_count", 0), primary_language=repository.get("language"), languages=languages_response.json(),
            default_branch=repository["default_branch"], size_kb=repository.get("size", 0),
        )

    async def download_source(self, repository: GitHubRepositoryData, destination: Path) -> None:
        archive_url = f"https://api.github.com/repos/{repository.owner}/{repository.name}/zipball/{repository.default_branch}"
        destination.mkdir(parents=True, exist_ok=True)
        archive_path = destination / "source.zip"
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=90.0, follow_redirects=True) as client:
                async with client.stream("GET", archive_url) as response:
                    self._raise_for_github_error(response, repository.owner, repository.name)
                    with archive_path.open("wb") as archive:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            archive.write(chunk)
            self._safe_extract(archive_path, destination)
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise
        finally:
            archive_path.unlink(missing_ok=True)

    @staticmethod
    def _safe_extract(archive_path: Path, destination: Path) -> None:
        root = destination.resolve()
        SKIP_EXTENSIONS = {
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff",
            ".mp4", ".webm", ".avi", ".mov", ".mp3", ".wav", ".pdf", ".zip", ".tar",
            ".gz", ".7z", ".rar", ".exe", ".dll", ".so", ".dylib", ".bin", ".iso",
            ".woff", ".woff2", ".ttf", ".eot", ".otf", ".psd", ".pyc", ".db", ".sqlite",
        }
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                ext = Path(member.filename).suffix.lower()
                if ext in SKIP_EXTENSIONS or member.file_size > 5_000_000:
                    continue
                target = (destination / member.filename).resolve()
                if root not in target.parents and target != root:
                    raise HTTPException(status_code=502, detail="GitHub returned an unsafe repository archive.")
                
                try:
                    win_target = _win_path(target)
                    win_target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source_file, open(win_target, "wb") as target_file:
                        shutil.copyfileobj(source_file, target_file)
                except (OSError, FileNotFoundError):
                    # Gracefully skip files with long/invalid Windows file names
                    continue

    @staticmethod
    def _raise_for_github_error(response: httpx.Response, owner: str, name: str) -> None:
        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid GITHUB_TOKEN configured in .env. Please check or remove your token.")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Public repository {owner}/{name} was not found.")
        if response.status_code == 403:
            raise HTTPException(status_code=429, detail="GitHub API rate limit reached. Configure GITHUB_TOKEN or wait a few minutes.")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise HTTPException(status_code=502, detail=f"GitHub error ({response.status_code}): Could not retrieve this repository.") from error


def repository_storage_path(repository_id: UUID) -> Path:
    return Path(get_settings().repository_storage_path) / str(repository_id)


class GitHubActivityClient(GitHubClient):
    async def get_commits(self, owner: str, name: str, per_page: int = 10) -> list[dict]:
        async with httpx.AsyncClient(base_url="https://api.github.com", headers=self.headers, timeout=30.0, follow_redirects=True) as client:
            r = await client.get(f"/repos/{owner}/{name}/commits", params={"per_page": per_page})
            self._raise_for_github_error(r, owner, name)
            return [
                {
                    "sha": c["sha"][:7],
                    "message": c["commit"]["message"].split("\n")[0],
                    "author": c["commit"]["author"]["name"],
                    "date": c["commit"]["author"]["date"],
                    "url": c["html_url"],
                }
                for c in r.json()
            ]

    async def get_issues(self, owner: str, name: str, per_page: int = 5, state: str = "open") -> list[dict]:
        async with httpx.AsyncClient(base_url="https://api.github.com", headers=self.headers, timeout=30.0, follow_redirects=True) as client:
            r = await client.get(f"/repos/{owner}/{name}/issues", params={"per_page": per_page, "state": state})
            self._raise_for_github_error(r, owner, name)
            return [
                {
                    "number": i["number"],
                    "title": i["title"],
                    "state": i["state"],
                    "author": i["user"]["login"] if i.get("user") else "unknown",
                    "comments": i.get("comments", 0),
                    "url": i["html_url"],
                    "created_at": i["created_at"],
                }
                for i in r.json() if "pull_request" not in i
            ]

    async def get_pull_requests(self, owner: str, name: str, per_page: int = 5, state: str = "open") -> list[dict]:
        async with httpx.AsyncClient(base_url="https://api.github.com", headers=self.headers, timeout=30.0, follow_redirects=True) as client:
            r = await client.get(f"/repos/{owner}/{name}/pulls", params={"per_page": per_page, "state": state})
            self._raise_for_github_error(r, owner, name)
            return [
                {
                    "number": pr["number"],
                    "title": pr["title"],
                    "state": pr["state"],
                    "author": pr["user"]["login"] if pr.get("user") else "unknown",
                    "url": pr["html_url"],
                    "created_at": pr["created_at"],
                }
                for pr in r.json()
            ]
