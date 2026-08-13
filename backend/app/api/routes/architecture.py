from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ArchitectureReport, Repository
from app.schemas import ArchitectureResponse
from app.services.architecture import analyze_repository

router = APIRouter()


def as_response(report: ArchitectureReport) -> ArchitectureResponse:
    return ArchitectureResponse(repository_id=report.repository_id, framework=report.framework, languages=report.languages, dependencies=report.dependencies, structure=report.structure, important_files=report.important_files, summary=report.summary, analyzed_at=report.analyzed_at)


@router.post("/{repository_id}/architecture", response_model=ArchitectureResponse, summary="Analyze repository architecture")
async def analyze_architecture(repository_id: UUID, session: AsyncSession = Depends(get_session)) -> ArchitectureResponse:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Imported repository not found.")
    source_path = Path(repository.source_path)
    if not source_path.exists():
        raise HTTPException(status_code=409, detail="The source snapshot is unavailable. Re-import the repository and try again.")
    analysis = analyze_repository(source_path)
    report = await session.get(ArchitectureReport, repository.id)
    if report is None:
        report = ArchitectureReport(repository_id=repository.id, framework=analysis.framework, languages=analysis.languages, dependencies=analysis.dependencies, structure=analysis.structure, important_files=analysis.important_files, summary=analysis.summary)
        session.add(report)
    else:
        report.framework, report.languages, report.dependencies = analysis.framework, analysis.languages, analysis.dependencies
        report.structure, report.important_files, report.summary = analysis.structure, analysis.important_files, analysis.summary
    await session.commit()
    await session.refresh(report)
    return as_response(report)


@router.get("/{repository_id}/architecture", response_model=ArchitectureResponse, summary="Get repository architecture")
async def get_architecture(repository_id: UUID, session: AsyncSession = Depends(get_session)) -> ArchitectureResponse:
    report = await session.get(ArchitectureReport, repository_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Architecture has not been generated for this repository.")
    return as_response(report)
