from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(511), unique=True, index=True, nullable=False)
    html_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    stars_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    forks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    primary_language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    languages: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    size_kb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    import_status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ArchitectureReport(Base):
    __tablename__ = "architecture_reports"

    repository_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True)
    framework: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    languages: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, nullable=False)
    dependencies: Mapped[dict[str, list[str]]] = mapped_column(JSON, default=dict, nullable=False)
    structure: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    important_files: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
