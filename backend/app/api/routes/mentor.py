import json
import re
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Repository
from app.schemas import ChatRequest, CodeExplanationRequest, GroundedAnswerResponse
from app.services.ai import answer_with_repository_context, stream_repository_context
from app.services.cache import TTL_CHAT, cache_get, cache_set
from app.services.retrieval import read_requested_file, retrieve_relevant_files

router = APIRouter()


def citations(answer: str, valid_paths: set[str]) -> list[str]:
    return sorted({match for match in re.findall(r"\[([^\]\n]+)\]", answer) if match in valid_paths})


async def repository_or_404(repository_id: UUID, session: AsyncSession) -> Repository:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Imported repository not found.")
    if not Path(repository.source_path).exists():
        raise HTTPException(status_code=409, detail="The source snapshot is unavailable. Re-import the repository and try again.")
    return repository


@router.post("/{repository_id}/chat", response_model=GroundedAnswerResponse, summary="Ask a question grounded in repository source")
async def chat_with_repository(repository_id: UUID, payload: ChatRequest, session: AsyncSession = Depends(get_session)) -> GroundedAnswerResponse:
    repository = await repository_or_404(repository_id, session)
    cache_key = (str(repository.id), payload.question.strip().lower())
    cached = await cache_get("chat", *cache_key)
    if cached:
        data = json.loads(cached)
        return GroundedAnswerResponse(answer=data["answer"], citations=data["citations"])

    excerpts = retrieve_relevant_files(Path(repository.source_path), payload.question)
    answer = await answer_with_repository_context(payload.question, excerpts)
    result = GroundedAnswerResponse(answer=answer, citations=citations(answer, {excerpt.path for excerpt in excerpts}))
    await cache_set("chat", json.dumps({"answer": result.answer, "citations": result.citations}), TTL_CHAT, *cache_key)
    return result


@router.post("/{repository_id}/chat/stream", summary="Stream a grounded chat response (SSE)")
async def chat_stream(repository_id: UUID, payload: ChatRequest, session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    repository = await repository_or_404(repository_id, session)
    excerpts = retrieve_relevant_files(Path(repository.source_path), payload.question)
    valid_paths = {excerpt.path for excerpt in excerpts}

    async def event_generator():
        collected: list[str] = []
        async for chunk in stream_repository_context(payload.question, excerpts):
            collected.append(chunk)
            yield f"data: {json.dumps({'type': 'delta', 'text': chunk})}\n\n"
        full_answer = "".join(collected)
        cites = citations(full_answer, valid_paths)
        yield f"data: {json.dumps({'type': 'done', 'citations': cites})}\n\n"
        _cache_key = (str(repository.id), payload.question.strip().lower())
        await cache_set("chat", json.dumps({"answer": full_answer, "citations": cites}), TTL_CHAT, *_cache_key)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{repository_id}/explain-file", response_model=GroundedAnswerResponse, summary="Explain a repository file")
async def explain_file(repository_id: UUID, payload: CodeExplanationRequest, session: AsyncSession = Depends(get_session)) -> GroundedAnswerResponse:
    repository = await repository_or_404(repository_id, session)
    cache_key = (str(repository.id), payload.file_path)
    cached = await cache_get("explain", *cache_key)
    if cached:
        data = json.loads(cached)
        return GroundedAnswerResponse(answer=data["answer"], citations=data["citations"])

    excerpt = read_requested_file(Path(repository.source_path), payload.file_path)
    question = f"Explain {excerpt.path} to a developer joining this project."
    answer = await answer_with_repository_context(question, [excerpt], mode="explain")
    result = GroundedAnswerResponse(answer=answer, citations=citations(answer, {excerpt.path}))
    await cache_set("explain", json.dumps({"answer": result.answer, "citations": result.citations}), TTL_CHAT, *cache_key)
    return result
