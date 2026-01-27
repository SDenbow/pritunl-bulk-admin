from __future__ import annotations

from .db import SessionLocal
from .auth.models import Admin


def is_bootstrapped() -> bool:
    """
    Returns True once at least one admin exists.
    This is the single source of truth for "setup complete" detection.
    """
    db = SessionLocal()
    try:
        return db.query(Admin).count() > 0
    finally:
        db.close()
