import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def stable_json_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def advisory_lock_key_from_str(s: str) -> int:
    d = hashlib.sha256(s.encode("utf-8")).digest()
    n = int.from_bytes(d[:8], byteorder="big", signed=False)
    if n >= 2**63:
        n = n - 2**64
    return n


def acquire_target_lock(db: Session, target_id: str):
    k = advisory_lock_key_from_str(target_id)
    db.execute(text("SELECT pg_advisory_lock(:k)"), {"k": k})


def release_target_lock(db: Session, target_id: str):
    k = advisory_lock_key_from_str(target_id)
    db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": k})


def now_utc():
    return datetime.now(timezone.utc)


def get_actor_from_request(request) -> str:
    try:
        from ..auth.session import get_session_username
        u = get_session_username(request)
        return u or "unknown"
    except Exception:
        return "unknown"
