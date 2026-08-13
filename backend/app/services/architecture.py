import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRECTORIES = {".git", "node_modules", ".next", "dist", "build", "coverage", ".venv", "venv", "vendor", "__pycache__"}
LANGUAGE_EXTENSIONS = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".swift": "Swift", ".vue": "Vue", ".svelte": "Svelte", ".html": "HTML", ".css": "CSS", ".scss": "SCSS"}
FRAMEWORK_MARKERS = {"next.config.js": "Next.js", "next.config.ts": "Next.js", "vite.config.ts": "Vite", "angular.json": "Angular", "manage.py": "Django", "flask": "Flask", "fastapi": "FastAPI", "rails": "Ruby on Rails", "Cargo.toml": "Rust", "go.mod": "Go"}
IMPORTANT_NAMES = {"readme.md", "package.json", "pyproject.toml", "requirements.txt", "docker-compose.yml", "docker-compose.yaml", "dockerfile", "main.py", "app.py", "manage.py", "next.config.ts", "next.config.js", "vite.config.ts"}


@dataclass(frozen=True)
class ArchitectureAnalysis:
    framework: list[str]
    languages: dict[str, int]
    dependencies: dict[str, list[str]]
    structure: list[str]
    important_files: list[str]
    summary: str


def analyze_repository(source_path: Path) -> ArchitectureAnalysis:
    root = _source_root(source_path)
    files = [path for path in root.rglob("*") if path.is_file() and not any(part in SKIP_DIRECTORIES for part in path.relative_to(root).parts)]
    language_counts = Counter(LANGUAGE_EXTENSIONS.get(path.suffix.lower()) for path in files)
    languages = {language: count for language, count in language_counts.items() if language}
    frameworks = _detect_frameworks(root, files)
    dependencies = _read_dependencies(root)
    structure = _tree(root, files)
    important_files = _important_files(root, files)
    summary = _summary(root, frameworks, languages, dependencies, important_files)
    return ArchitectureAnalysis(framework=frameworks, languages=languages, dependencies=dependencies, structure=structure, important_files=important_files, summary=summary)


def _source_root(source_path: Path) -> Path:
    children = [path for path in source_path.iterdir() if path.is_dir() and path.name not in SKIP_DIRECTORIES]
    return children[0] if len(children) == 1 else source_path


def _detect_frameworks(root: Path, files: list[Path]) -> list[str]:
    names = {path.name.lower() for path in files}
    detected = {framework for marker, framework in FRAMEWORK_MARKERS.items() if marker.lower() in names}
    package = _read_json(root / "package.json")
    package_dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})} if package else {}
    for dependency, framework in {"next": "Next.js", "react": "React", "fastapi": "FastAPI", "django": "Django", "flask": "Flask", "express": "Express", "@nestjs/core": "NestJS", "vue": "Vue", "svelte": "Svelte"}.items():
        if dependency in package_dependencies:
            detected.add(framework)
    requirements = _read_requirements(root)
    for dependency, framework in {"fastapi": "FastAPI", "django": "Django", "flask": "Flask"}.items():
        if dependency in requirements:
            detected.add(framework)
    return sorted(detected)


def _read_dependencies(root: Path) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    package = _read_json(root / "package.json")
    if package:
        groups["npm"] = sorted({*package.get("dependencies", {}).keys(), *package.get("devDependencies", {}).keys()})[:30]
    requirements = _read_requirements(root)
    if requirements:
        groups["python"] = sorted(requirements)[:30]
    return groups


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _read_requirements(root: Path) -> set[str]:
    paths = [root / "requirements.txt", root / "pyproject.toml"]
    dependencies: set[str] = set()
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.splitlines():
            candidate = line.strip().split("#", 1)[0].strip()
            if candidate and not candidate.startswith(("[", "#", "-", "python")):
                dependencies.add(candidate.split("=", 1)[0].split(">", 1)[0].split("<", 1)[0].split("[", 1)[0].strip().lower())
    return dependencies


def _tree(root: Path, files: list[Path]) -> list[str]:
    entries: set[str] = set()
    for file_path in files:
        parts = file_path.relative_to(root).parts
        for depth in range(1, min(len(parts), 4) + 1):
            segment = Path(*parts[:depth])
            entries.add(f"{'  ' * (depth - 1)}{'📄 ' if depth == len(parts) else '📁 '}{segment.name}")
    return sorted(entries, key=lambda item: item.replace("📁", "0").replace("📄", "1"))[:180]


def _important_files(root: Path, files: list[Path]) -> list[str]:
    candidates = [path for path in files if path.name.lower() in IMPORTANT_NAMES]
    candidates.sort(key=lambda path: (len(path.relative_to(root).parts), path.relative_to(root).as_posix()))
    return [path.relative_to(root).as_posix() for path in candidates[:20]]


def _summary(root: Path, frameworks: list[str], languages: dict[str, int], dependencies: dict[str, list[str]], important_files: list[str]) -> str:
    stack = ", ".join(frameworks) if frameworks else "a custom application stack"
    language = max(languages, key=languages.get) if languages else "mixed source files"
    dependency_note = f" It declares {sum(len(group) for group in dependencies.values())} top-level dependencies." if dependencies else ""
    entry_note = f" Start with {important_files[0]}." if important_files else ""
    return f"This repository is primarily {language} and appears to use {stack}.{dependency_note}{entry_note} The visual structure below is derived directly from its downloaded source snapshot."
