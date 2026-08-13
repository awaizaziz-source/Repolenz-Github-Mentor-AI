import shutil
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.models import Repository
from app.schemas import ActivityResponse, FileContentResponse, FileListResponse, ReadmeResponse, RepositoryImportRequest, RepositoryResponse
from app.services.github import GitHubActivityClient, GitHubClient, parse_github_repository_url, repository_storage_path
from app.services.retrieval import list_source_files, read_requested_file

router = APIRouter()


@router.post("/import", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED, summary="Import a public GitHub repository")
async def import_repository(payload: RepositoryImportRequest, session: AsyncSession = Depends(get_session)) -> Repository:
    owner, name = parse_github_repository_url(str(payload.repository_url))
    client = GitHubClient()
    remote_repository = await client.get_repository(owner, name)
    existing = await session.scalar(select(Repository).where(Repository.full_name == remote_repository.full_name))

    # Re-use existing only if it is marked "ready" AND its destination folder actually contains files
    if existing and existing.import_status == "ready" and Path(existing.source_path).exists():
        try:
            if any(Path(existing.source_path).iterdir()):
                return existing
        except OSError:
            pass

    repository = existing or Repository(
        owner=remote_repository.owner, name=remote_repository.name, full_name=remote_repository.full_name, html_url=remote_repository.html_url,
        description=remote_repository.description, owner_avatar_url=remote_repository.owner_avatar_url, stars_count=remote_repository.stars_count,
        forks_count=remote_repository.forks_count, primary_language=remote_repository.primary_language, languages=remote_repository.languages,
        default_branch=remote_repository.default_branch, size_kb=remote_repository.size_kb, source_path="", import_status="downloading",
    )
    if not existing:
        session.add(repository)
        await session.flush()

    dest_path = repository_storage_path(repository.id)
    repository.source_path = str(dest_path)
    repository.import_status = "downloading"
    try:
        await client.download_source(remote_repository, dest_path)
    except Exception as exc:
        repository.import_status = "download_failed"
        shutil.rmtree(dest_path, ignore_errors=True)
        await session.commit()
        detail_msg = exc.detail if isinstance(exc, HTTPException) else str(exc)
        raise HTTPException(status_code=502, detail=f"Failed to download repository: {detail_msg}")

    repository.import_status = "ready"
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        duplicate = await session.scalar(select(Repository).where(Repository.full_name == remote_repository.full_name))
        if duplicate is not None:
            return duplicate
        raise
    await session.refresh(repository)
    return repository


@router.get("/{repository_id}", response_model=RepositoryResponse, summary="Get an imported repository")
async def get_repository(repository_id: UUID, session: AsyncSession = Depends(get_session)) -> Repository:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Imported repository not found.")
    return repository


@router.get("/{repository_id}/files", response_model=FileListResponse, summary="List browsable source files")
async def list_files(repository_id: UUID, session: AsyncSession = Depends(get_session)) -> FileListResponse:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Imported repository not found.")
    source_path = Path(repository.source_path)
    if not source_path.exists():
        raise HTTPException(status_code=409, detail="The source snapshot is unavailable. Re-import the repository and try again.")
    files = list_source_files(source_path)
    return FileListResponse(repository_id=repository.id, files=files, total=len(files))


@router.get("/{repository_id}/content", response_model=FileContentResponse, summary="Read a file from the repository")
async def read_file(repository_id: UUID, path: str = Query(..., min_length=1, max_length=1024), session: AsyncSession = Depends(get_session)) -> FileContentResponse:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Imported repository not found.")
    source_path = Path(repository.source_path)
    if not source_path.exists():
        raise HTTPException(status_code=409, detail="The source snapshot is unavailable.")
    excerpt = read_requested_file(source_path, path)
    ext = Path(path).suffix.lstrip(".") if "." in Path(path).name else None
    return FileContentResponse(repository_id=repository.id, path=excerpt.path, content=excerpt.content, language=ext)


@router.get("/{repository_id}/readme", response_model=ReadmeResponse, summary="Get README content")
async def get_readme(repository_id: UUID, session: AsyncSession = Depends(get_session)) -> ReadmeResponse:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Imported repository not found.")
    source_path = Path(repository.source_path)
    if not source_path.exists():
        raise HTTPException(status_code=409, detail="The source snapshot is unavailable.")
    readme_candidates = list_source_files(source_path, globs=["README.md", "readme.md", "Readme.md"])
    if not readme_candidates:
        all_files = list_source_files(source_path)
        readme_candidates = [f for f in all_files if f.lower().endswith("readme.md")]
    if not readme_candidates:
        raise HTTPException(status_code=404, detail="No README file found in this repository.")
    excerpt = read_requested_file(source_path, readme_candidates[0])
    return ReadmeResponse(repository_id=repository.id, content=excerpt.content)


@router.get("/{repository_id}/activity", response_model=ActivityResponse, summary="Get recent commits, issues, and PRs from GitHub")
async def get_activity(repository_id: UUID, session: AsyncSession = Depends(get_session)) -> ActivityResponse:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Imported repository not found.")
    client = GitHubActivityClient()
    commits = await client.get_commits(repository.owner, repository.name)
    issues = await client.get_issues(repository.owner, repository.name)
    pulls = await client.get_pull_requests(repository.owner, repository.name)
    return ActivityResponse(repository_id=repository.id, commits=commits, issues=issues, pull_requests=pulls)
