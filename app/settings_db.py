from sqlalchemy import Integer, Boolean, DateTime, func, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="global")

    warn_disable_count: Mapped[int] = mapped_column(Integer, default=5)
    warn_delete_count: Mapped[int] = mapped_column(Integer, default=1)
    warn_group_clear_count: Mapped[int] = mapped_column(Integer, default=5)
    warn_create_count: Mapped[int] = mapped_column(Integer, default=10)

    require_typed_confirm: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
