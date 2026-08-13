from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Repository
from app.schemas import CodeReviewResponse, DocumentationRequest, DocumentationResponse, OnboardingResponse
from app.services.ai import generate_code_review, generate_documentation, generate_onboarding_roadmap
from app.services.cache import TTL_CODE_REVIEW, TTL_DOCUMENTATION, TTL_ONBOARDING, cache_get, cache_set

router = APIRouter()


async def _get_ready_repository(repository_id: UUID, session: AsyncSession) -> Repository:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Imported repository not found.")
    if not Path(repository.source_path).exists():
        raise HTTPException(status_code=409, detail="The source snapshot is unavailable. Re-import the repository and try again.")
    return repository


def _cache_key(repository: Repository, *parts: str) -> tuple[str, ...]:
    return (str(repository.id), repository.updated_at.isoformat(), *parts)


@router.post(
    "/{repository_id}/code-review",
    response_model=CodeReviewResponse,
    summary="Generate an AI code review for the repository",
)
async def code_review(repository_id: UUID, session: AsyncSession = Depends(get_session)) -> CodeReviewResponse:
    repository = await _get_ready_repository(repository_id, session)
    _key = _cache_key(repository)
    cached = await cache_get("review", *_key)
    if cached:
        return CodeReviewResponse(repository_id=str(repository.id), report=cached)

    report = await generate_code_review(Path(repository.source_path))
    await cache_set("review", report, TTL_CODE_REVIEW, *_key)
    return CodeReviewResponse(repository_id=str(repository.id), report=report)


@router.post(
    "/{repository_id}/documentation",
    response_model=DocumentationResponse,
    summary="Generate documentation for the repository",
)
async def generate_docs(
    repository_id: UUID,
    payload: DocumentationRequest,
    session: AsyncSession = Depends(get_session),
) -> DocumentationResponse:
    repository = await _get_ready_repository(repository_id, session)
    _key = _cache_key(repository, payload.doc_type)
    cached = await cache_get("docs", *_key)
    if cached:
        return DocumentationResponse(repository_id=str(repository.id), doc_type=payload.doc_type, content=cached)

    content = await generate_documentation(Path(repository.source_path), payload.doc_type)
    await cache_set("docs", content, TTL_DOCUMENTATION, *_key)
    return DocumentationResponse(repository_id=str(repository.id), doc_type=payload.doc_type, content=content)


@router.post(
    "/{repository_id}/onboarding",
    response_model=OnboardingResponse,
    summary="Generate a developer onboarding roadmap",
)
async def onboarding_roadmap(repository_id: UUID, session: AsyncSession = Depends(get_session)) -> OnboardingResponse:
    repository = await _get_ready_repository(repository_id, session)
    _key = _cache_key(repository)
    cached = await cache_get("onboarding", *_key)
    if cached:
        return OnboardingResponse(repository_id=str(repository.id), roadmap=cached)

    roadmap = await generate_onboarding_roadmap(Path(repository.source_path))
    await cache_set("onboarding", roadmap, TTL_ONBOARDING, *_key)
    return OnboardingResponse(repository_id=str(repository.id), roadmap=roadmap)
