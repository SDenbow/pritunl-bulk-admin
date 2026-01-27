import json
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..auth.routes import require_login
from ..importer.models import AuditLog
from ..targets.models import Target

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


REDACT_KEYS = {
    "password", "pass", "passwd",
    "api_secret", "secret", "token", "api_token",
    "authorization", "auth", "cookie", "set-cookie",
    "session", "session_secret",
    "totp", "totp_secret",
}


def _redact(obj):
    """Recursively redact sensitive fields before displaying in UI."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in REDACT_KEYS or any(x in lk for x in ["password", "secret", "token", "auth", "cookie"]):
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


@router.get("/history")
def history_list(
    request: Request,
    target_id: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    operation: str | None = Query(default=None),
    email: str | None = Query(default=None),
    success: str | None = Query(default=None),  # "true"|"false"
    batch_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=25, le=1000),
    db: Session = Depends(get_db),
):
    redir = require_login(request)
    if redir:
        return redir

    q = db.query(AuditLog)

    if target_id:
        q = q.filter(AuditLog.target_id == target_id)
    if actor:
        q = q.filter(AuditLog.actor.ilike(f"%{actor.strip()}%"))
    if operation:
        q = q.filter(AuditLog.operation.ilike(f"%{operation.strip()}%"))
    if email:
        q = q.filter(AuditLog.email.ilike(f"%{email.strip()}%"))
    if batch_id:
        q = q.filter(AuditLog.batch_id == batch_id.strip())
    if success in ("true", "false"):
        q = q.filter(AuditLog.success == (success == "true"))

    logs = q.order_by(AuditLog.ts.desc()).limit(limit).all()

    # Map target_id -> target name for display (so "where" is human-readable)
    targets = db.query(Target).all()
    target_map = {t.id: t.name for t in targets}

    # Provide dropdown options
    target_options = sorted([(t.id, t.name) for t in targets], key=lambda x: x[1].lower())

    return _templates(request).TemplateResponse(
        "history.html",
        {
            "request": request,
            "logs": logs,
            "target_map": target_map,
            "target_options": target_options,
            "filters": {
                "target_id": target_id or "",
                "actor": actor or "",
                "operation": operation or "",
                "email": email or "",
                "success": success or "",
                "batch_id": batch_id or "",
                "limit": limit,
            },
        },
    )


@router.get("/history/{log_id}")
def history_detail(request: Request, log_id: str, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir

    log = db.query(AuditLog).filter(AuditLog.id == log_id).first()
    if not log:
        return RedirectResponse(url="/history", status_code=303)

    target = db.query(Target).filter(Target.id == log.target_id).first()
    target_name = target.name if target else log.target_id

    safe_request = _redact(log.request or {})
    safe_response = _redact(log.response or {})

    return _templates(request).TemplateResponse(
        "history_detail.html",
        {
            "request": request,
            "log": log,
            "target_name": target_name,
            "safe_request_json": json.dumps(safe_request, indent=2, sort_keys=True),
            "safe_response_json": json.dumps(safe_response, indent=2, sort_keys=True),
        },
    )
