import pytest
from pathlib import Path

from app.services.github import parse_github_repository_url
from app.services.retrieval import retrieve_relevant_files


def test_parse_github_repository_url_accepts_standard_url() -> None:
    owner, name = parse_github_repository_url("https://github.com/tiangolo/fastapi")
    assert owner == "tiangolo"
    assert name == "fastapi"


def test_retrieve_relevant_files_falls_back_when_no_keyword_match(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    (tmp_path / "readme.md").write_text("# Demo\n", encoding="utf-8")

    excerpts = retrieve_relevant_files(tmp_path, "explain this repo to a beginner")
    assert len(excerpts) > 0
    paths = {excerpt.path for excerpt in excerpts}
    assert "main.py" in paths or "readme.md" in paths
