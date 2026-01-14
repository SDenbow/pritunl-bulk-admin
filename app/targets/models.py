import uuid
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    base_url: Mapped[str] = mapped_column(String)

    auth_mode: Mapped[str] = mapped_column(String)  # enterprise_hmac | session_login
    verify_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_groups: Mapped[bool] = mapped_column(Boolean, default=False)

    org_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # encrypted JSON blob containing credentials
    credentials_enc: Mapped[str] = mapped_column(String)

    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
