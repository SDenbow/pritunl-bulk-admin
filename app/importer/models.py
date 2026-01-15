import uuid
from sqlalchemy import String, Boolean, DateTime, func, LargeBinary, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    target_id: Mapped[str] = mapped_column(String, index=True)
    created_by: Mapped[str] = mapped_column(String, default="unknown")

    status: Mapped[str] = mapped_column(String, default="previewed")  # previewed|applying|applied|failed

    # Immutable snapshot
    csv_sha256: Mapped[str] = mapped_column(String, index=True)
    csv_bytes: Mapped[bytes] = mapped_column(LargeBinary)

    # Hash of the preview plan shown to the user (prevents tampering)
    preview_sha256: Mapped[str] = mapped_column(String, index=True)

    # Store summary & meta for UI + safety checks
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class ImportRow(Base):
    __tablename__ = "import_rows"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id: Mapped[str] = mapped_column(String, index=True)

    row_num: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, index=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String)  # ok|skip|error

    before: Mapped[str] = mapped_column(String, default="")
    after: Mapped[str] = mapped_column(String, default="")
    error: Mapped[str | None] = mapped_column(String, nullable=True)

    desired: Mapped[dict] = mapped_column(JSONB, default=dict)
    diff: Mapped[dict] = mapped_column(JSONB, default=dict)

    will_apply: Mapped[bool] = mapped_column(Boolean, default=False)

    apply_status: Mapped[str] = mapped_column(String, default="pending")  # pending|skipped|applied|failed
    apply_result: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    applied_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ts: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actor: Mapped[str] = mapped_column(String, default="unknown")
    target_id: Mapped[str] = mapped_column(String, index=True)
    batch_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    row_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    email: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    operation: Mapped[str] = mapped_column(String)

    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)

    request: Mapped[dict] = mapped_column(JSONB, default=dict)
    response: Mapped[dict] = mapped_column(JSONB, default=dict)
