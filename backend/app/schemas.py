from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class RepositoryImportRequest(BaseModel):
    repository_url: HttpUrl = Field(description="Public GitHub repository URL")


class RepositoryResponse(BaseModel):
    id: UUID
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
    import_status: str
    imported_at: datetime

    model_config = {"from_attributes": True}


class ArchitectureResponse(BaseModel):
    repository_id: UUID
    framework: list[str]
    languages: dict[str, int]
    dependencies: dict[str, list[str]]
    structure: list[str]
    important_files: list[str]
    summary: str
    analyzed_at: datetime


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)


class CodeExplanationRequest(BaseModel):
    file_path: str = Field(min_length=1, max_length=1_024)


class GroundedAnswerResponse(BaseModel):
    answer: str
    citations: list[str]


class CodeReviewResponse(BaseModel):
    repository_id: str
    report: str


class DocumentationRequest(BaseModel):
    doc_type: Literal["readme", "installation", "api", "developer", "architecture", "contributing"] = Field(
        default="readme",
        description="Type of documentation to generate",
    )


class DocumentationResponse(BaseModel):
    repository_id: str
    doc_type: str
    content: str


class OnboardingResponse(BaseModel):
    repository_id: str
    roadmap: str


class FileListResponse(BaseModel):
    repository_id: UUID
    files: list[str]
    total: int


class FileContentResponse(BaseModel):
    repository_id: UUID
    path: str
    content: str
    language: str | None


class ReadmeResponse(BaseModel):
    repository_id: UUID
    content: str


class ActivityResponse(BaseModel):
    repository_id: UUID
    commits: list[dict]
    issues: list[dict]
    pull_requests: list[dict]
