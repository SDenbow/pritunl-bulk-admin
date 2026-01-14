import csv
import io
import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response
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


@router.get("/targets/{target_id}/export.csv")
def target_export_csv(request: Request, target_id: str, db: Session = Depends(get_db)):
    """
    Read-only export of users to CSV.
    Currently implemented for enterprise_hmac targets only.
    """
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    if t.auth_mode != "enterprise_hmac":
        return Response("Export is implemented for enterprise_hmac targets only (for now).", status_code=400)

    # Fetch users from Pritunl
    client = build_client(t)
    orgs = client.list_organizations()
    chosen = choose_org(orgs, t.org_name)
    org_id = chosen.get("id")
    if not org_id:
        return Response("Chosen org did not include an 'id' field.", status_code=500)

    users = client.list_users(org_id)
    if not isinstance(users, list):
        return Response("Unexpected user list format from target.", status_code=500)

    # Build CSV
    buf = io.StringIO()
    w = csv.writer(buf)

    # Header
    w.writerow(["action", "username", "email", "disabled", "groups"])

    for u in users:
        username = (u.get("name") or "").strip()
        email = (u.get("email") or "").strip()
        disabled = bool(u.get("disabled", False))

        groups = u.get("groups") or []
        if isinstance(groups, list):
            groups_str = ",".join([str(g).strip() for g in groups if str(g).strip()])
        else:
            groups_str = str(groups).strip()

        w.writerow(["", username, email, "true" if disabled else "false", groups_str])

    csv_bytes = buf.getvalue().encode("utf-8")

    filename = f"{t.name}_users.csv".replace(" ", "_")
    headers = {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return Response(content=csv_bytes, headers=headers)


@router.get("/targets/{target_id}/edit")
def target_edit_get(request: Request, target_id: str, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    return _templates(request).TemplateResponse(
        "target_edit.html",
        {"request": request, "target": t, "error": None},
    )


@router.post("/targets/{target_id}/edit")
def target_edit_post(
    request: Request,
    target_id: str,
    name: str = Form(...),
    base_url: str = Form(...),
    auth_mode: str = Form(...),
    verify_tls: str = Form(default=""),
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

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    t.name = name.strip()
    t.base_url = base_url.strip()
    t.auth_mode = auth_mode
    t.verify_tls = (verify_tls == "on")
    t.supports_groups = (supports_groups == "on")
    t.org_name = org_name.strip() or None

    # Credentials: only replace if provided (so we never show secrets)
    replace_creds = False
    new_creds = None

    if auth_mode == "enterprise_hmac":
        if api_token.strip() or api_secret.strip():
            if not api_token.strip() or not api_secret.strip():
                return _templates(request).TemplateResponse(
                    "target_edit.html",
                    {"request": request, "target": t, "error": "To update Enterprise credentials, provide BOTH API Token and API Secret."},
                )
            new_creds = {"api_token": api_token.strip(), "api_secret": api_secret.strip()}
            replace_creds = True

    elif auth_mode == "session_login":
        if login_user.strip() or login_pass:
            if not login_user.strip() or not login_pass:
                return _templates(request).TemplateResponse(
                    "target_edit.html",
                    {"request": request, "target": t, "error": "To update Session Login credentials, provide BOTH username and password."},
                )
            new_creds = {"username": login_user.strip(), "password": login_pass}
            replace_creds = True
    else:
        return _templates(request).TemplateResponse(
            "target_edit.html",
            {"request": request, "target": t, "error": "Invalid auth_mode."},
        )

    if replace_creds and new_creds is not None:
        t.credentials_enc = encrypt_str(json.dumps(new_creds))

    db.add(t)
    db.commit()

    return RedirectResponse(f"/targets/{t.id}", status_code=303)


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
