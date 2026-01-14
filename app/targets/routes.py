import json
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..crypto import encrypt_str
from .models import Target
from ..auth.routes import require_login
from ..pritunl.service import build_client, choose_org

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


@router.get("/targets")
def targets_list(request: Request, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir
    targets = db.query(Target).order_by(Target.name.asc()).all()
    return _templates(request).TemplateResponse("targets.html", {"request": request, "targets": targets, "error": None})


@router.post("/targets")
def targets_create(
    request: Request,
    name: str = Form(...),
    base_url: str = Form(...),
    auth_mode: str = Form(...),
    verify_tls: str = Form(default="on"),
    supports_groups: str = Form(default=""),
    org_name: str = Form(default=""),
    api_token: str = Form(default=""),
    api_secret: str = Form(default=""),
    login_user: str = Form(default=""),
    login_pass: str = Form(default=""),
    db: Session = Depends(get_db),
):
    redir = require_login(request)
    if redir:
        return redir

    verify = verify_tls == "on"
    groups = supports_groups == "on"

    if auth_mode == "enterprise_hmac":
        creds = {"api_token": api_token.strip(), "api_secret": api_secret.strip()}
    elif auth_mode == "session_login":
        creds = {"username": login_user.strip(), "password": login_pass}
    else:
        targets = db.query(Target).order_by(Target.name.asc()).all()
        return _templates(request).TemplateResponse(
            "targets.html",
            {"request": request, "targets": targets, "error": "Invalid auth_mode"},
        )

    t = Target(
        name=name.strip(),
        base_url=base_url.strip(),
        auth_mode=auth_mode,
        verify_tls=verify,
        supports_groups=groups,
        org_name=org_name.strip() or None,
        credentials_enc=encrypt_str(json.dumps(creds)),
    )

    db.add(t)
    db.commit()
    return RedirectResponse("/targets", status_code=303)


@router.get("/targets/{target_id}")
def target_detail(request: Request, target_id: str, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    return _templates(request).TemplateResponse(
        "target_detail.html",
        {"request": request, "target": t, "result": None, "error": None},
    )


@router.post("/targets/{target_id}/test")
def target_test_connection(request: Request, target_id: str, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    if t.auth_mode != "enterprise_hmac":
        return _templates(request).TemplateResponse(
            "target_detail.html",
            {"request": request, "target": t, "result": None, "error": "Test is implemented for enterprise_hmac only (for now)."},
        )

    try:
        client = build_client(t)
        orgs = client.list_organizations()
        chosen = choose_org(orgs, t.org_name)
        org_id = chosen.get("id")
        org_name = chosen.get("name")

        if not org_id:
            raise RuntimeError("Chosen org did not include an 'id' field")

        users = client.list_users(org_id)

        result = {
            "org_name": org_name,
            "org_id": org_id,
            "user_count": len(users) if isinstance(users, list) else None,
            "sample_users": [
                {
                    "name": u.get("name"),
                    "email": u.get("email"),
                    "disabled": u.get("disabled"),
                    "groups": u.get("groups"),
                }
                for u in (users[:10] if isinstance(users, list) else [])
            ],
        }

        return _templates(request).TemplateResponse(
            "target_detail.html",
            {"request": request, "target": t, "result": result, "error": None},
        )

    except Exception as e:
        return _templates(request).TemplateResponse(
            "target_detail.html",
            {"request": request, "target": t, "result": None, "error": str(e)},
        )
