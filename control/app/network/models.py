from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from shared.config.environment import resolve_environment


class Base(DeclarativeBase):
    pass


class ProxyProfile(Base):
    __tablename__ = "proxy_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    scope: Mapped[str] = mapped_column(String(48), nullable=False, default="global", index=True)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transport: Mapped[str | None] = mapped_column(String(48), nullable=True)
    security: Mapped[str | None] = mapped_column(String(48), nullable=True)
    sni: Mapped[str | None] = mapped_column(String(255), nullable=True)
    flow: Mapped[str | None] = mapped_column(String(80), nullable=True)
    path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fallback_direct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    health_check_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    secret_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


def _default_sqlite_url() -> str:
    configured = resolve_environment(
        "OMERTA_CONTROL_DATA_DIR",
        aliases=("AION_CONTROL_DATA_DIR",),
        default=".aion",
    )
    assert isinstance(configured, str)
    data_dir = Path(configured)
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'control.db'}"


DATABASE_URL = (
    resolve_environment(
        "OMERTA_CONTROL_DATABASE_URL",
        aliases=("AION_CONTROL_DATABASE_URL",),
    )
    or resolve_environment(
        "OMERTA_CONTROL_POSTGRES_DSN",
        aliases=("AION_CONTROL_POSTGRES_DSN",),
    )
    or os.getenv("DATABASE_URL")
    or _default_sqlite_url()
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
