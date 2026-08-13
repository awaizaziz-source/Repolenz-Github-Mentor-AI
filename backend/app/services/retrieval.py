import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from app.services.architecture import SKIP_DIRECTORIES, _source_root

TEXT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".cs", ".md", ".json", ".yml", ".yaml", ".toml", ".html", ".css", ".sql", ".sh", ".env.example", ".svelte", ".vue"}
MAX_FILE_BYTES = 160_000
MAX_CONTEXT_CHARS = 28_000


@dataclass(frozen=True)
class SourceExcerpt:
    path: str
    content: str


def list_source_files(source_path: Path, limit: int = 500, globs: list[str] | None = None) -> list[str]:
    """Return relative paths of readable source files for file browsing."""
    root = _source_root(source_path)
    if globs:
        paths: list[tuple[int, str]] = []
        for pattern in globs:
            for path in root.rglob(pattern):
                if path.is_file():
                    rel = path.relative_to(root).as_posix()
                    paths.append((0, rel))
        return [p for _, p in paths]
    paths = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        parts = path.relative_to(root).parts
        if any(part in SKIP_DIRECTORIES for part in parts):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        relative = path.relative_to(root).as_posix()
        paths.append((len(parts), relative))
    paths.sort(key=lambda item: (item[0], item[1].lower()))
    return [relative for _, relative in paths[:limit]]


def retrieve_relevant_files(source_path: Path, question: str, limit: int = 8) -> list[SourceExcerpt]:
    root = _source_root(source_path)
    terms = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", question.lower()))
    scored: list[tuple[int, Path]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS or any(part in SKIP_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        relative = path.relative_to(root).as_posix().lower()
        score = sum(relative.count(term) * 8 + content.lower().count(term) for term in terms)
        if score:
            scored.append((score, path))
    scored.sort(key=lambda item: (-item[0], item[1].as_posix()))

    # Fallback: broad questions (e.g. "explain to a beginner") often match no keywords
    if not scored:
        return _collect_all_files(source_path, max_files=limit, max_chars=MAX_CONTEXT_CHARS)

    excerpts: list[SourceExcerpt] = []
    remaining = MAX_CONTEXT_CHARS
    for _, path in scored[:limit]:
        content = path.read_text(encoding="utf-8", errors="ignore")
        clipped = content[: min(len(content), remaining)]
        if not clipped:
            break
        excerpts.append(SourceExcerpt(path=path.relative_to(root).as_posix(), content=clipped))
        remaining -= len(clipped)
    return excerpts


def _collect_all_files(source_path: Path, max_files: int = 20, max_chars: int = 32_000) -> list[SourceExcerpt]:
    """Collect the most representative files from the repository for broad analysis."""
    root = _source_root(source_path)
    # Priority: important files first, then by smallest depth, then alphabetically
    PRIORITY_NAMES = {
        "main.py", "app.py", "index.ts", "index.js", "server.ts", "server.js",
        "manage.py", "settings.py", "config.py", "routes.py", "router.py",
        "models.py", "schemas.py", "auth.py", "api.py", "utils.py",
        "package.json", "requirements.txt", "docker-compose.yml", "dockerfile",
        "readme.md", ".env.example",
    }
    candidates: list[tuple[int, int, Path]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        parts = path.relative_to(root).parts
        if any(part in SKIP_DIRECTORIES for part in parts):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        priority = 0 if path.name.lower() in PRIORITY_NAMES else 1
        depth = len(parts)
        candidates.append((priority, depth, path))

    candidates.sort(key=lambda t: (t[0], t[1], t[2].as_posix()))
    excerpts: list[SourceExcerpt] = []
    remaining = max_chars
    for _, _, path in candidates[:max_files]:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        clipped = content[: min(len(content), remaining)]
        if not clipped:
            break
        excerpts.append(SourceExcerpt(path=path.relative_to(root).as_posix(), content=clipped))
        remaining -= len(clipped)
        if remaining <= 0:
            break
    return excerpts


def read_requested_file(source_path: Path, requested_path: str) -> SourceExcerpt:
    root = _source_root(source_path).resolve()
    candidate = (root / requested_path).resolve()
    if root not in candidate.parents or not candidate.is_file():
        raise HTTPException(status_code=404, detail="The requested file was not found in the imported repository.")
    if candidate.stat().st_size > MAX_FILE_BYTES:
        raise HTTPException(status_code=422, detail="This file is too large to explain safely.")
    try:
        content = candidate.read_text(encoding="utf-8", errors="ignore")
    except OSError as error:
        raise HTTPException(status_code=422, detail="This file cannot be read as text.") from error
    return SourceExcerpt(path=candidate.relative_to(root).as_posix(), content=content)
