import secrets
import string

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.hash import argon2

from ..db import get_db
from ..auth.session import get_session_username
from ..auth.models import Admin
from ..settings_service import get_settings

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


def _current_admin(request: Request, db: Session) -> Admin | None:
    u = get_session_username(request)
    if not u:
        return None
    return db.query(Admin).filter(Admin.username == u).first()


def require_superadmin(request: Request, db: Session) -> RedirectResponse | None:
    a = _current_admin(request, db)
    if not a:
        return RedirectResponse(url="/login", status_code=303)
    if a.is_disabled:
        return RedirectResponse(url="/login", status_code=303)
    if not a.is_superadmin:
        return RedirectResponse(url="/targets", status_code=303)
    return None


def _superadmin_count(db: Session) -> int:
    return db.query(Admin).filter(Admin.is_superadmin == True, Admin.is_disabled == False).count()  # noqa: E712


def _gen_temp_password(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


@router.get("/superadmin")
def superadmin_home(request: Request, db: Session = Depends(get_db)):
    redir = require_superadmin(request, db)
    if redir:
        return redir

    settings = get_settings(db)
    admins = db.query(Admin).order_by(Admin.username.asc()).all()

    return _templates(request).TemplateResponse(
        "superadmin.html",
        {"request": request, "admins": admins, "settings": settings, "error": None, "message": None, "temp_password": None},
    )


@router.post("/superadmin/settings/update")
def superadmin_update_settings(
    request: Request,
    warn_disable_count: int = Form(...),
    warn_delete_count: int = Form(...),
    warn_group_clear_count: int = Form(...),
    warn_create_count: int = Form(...),
    require_typed_confirm: str = Form(default=""),
    db: Session = Depends(get_db),
):
    redir = require_superadmin(request, db)
    if redir:
        return redir

    s = get_settings(db)
    s.warn_disable_count = int(warn_disable_count)
    s.warn_delete_count = int(warn_delete_count)
    s.warn_group_clear_count = int(warn_group_clear_count)
    s.warn_create_count = int(warn_create_count)
    s.require_typed_confirm = (require_typed_confirm == "on")

    db.add(s)
    db.commit()
    return RedirectResponse("/superadmin", status_code=303)


@router.post("/superadmin/admins/create")
def superadmin_create_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    is_superadmin: str = Form(default=""),
    db: Session = Depends(get_db),
):
    redir = require_superadmin(request, db)
    if redir:
        return redir

    uname = username.strip()
    if not uname:
        return RedirectResponse("/superadmin", status_code=303)

    if db.query(Admin).filter(Admin.username == uname).first():
        return _templates(request).TemplateResponse(
            "superadmin.html",
            {"request": request, "admins": db.query(Admin).order_by(Admin.username.asc()).all(), "settings": get_settings(db),
             "error": "Admin already exists", "message": None, "temp_password": None},
        )

    a = Admin(
        username=uname,
        password_hash=argon2.hash(password),
        is_totp_enabled=False,
        totp_secret_enc=None,
        is_superadmin=(is_superadmin == "on"),
        is_disabled=False,
        force_password_change=False,
    )
    db.add(a)
    db.commit()
    return RedirectResponse("/superadmin", status_code=303)


@router.post("/superadmin/admins/toggle_superadmin")
def superadmin_toggle_superadmin(
    request: Request,
    admin_id: str = Form(...),
    make_superadmin: str = Form(...),  # "true" | "false"
    db: Session = Depends(get_db),
):
    redir = require_superadmin(request, db)
    if redir:
        return redir

    a = db.query(Admin).filter(Admin.id == admin_id).first()
    if not a:
        return RedirectResponse("/superadmin", status_code=303)

    want = (make_superadmin == "true")

    if not want:
        if a.is_superadmin and _superadmin_count(db) <= 1:
            return _templates(request).TemplateResponse(
                "superadmin.html",
                {"request": request, "admins": db.query(Admin).order_by(Admin.username.asc()).all(), "settings": get_settings(db),
                 "error": "Cannot remove the last super admin.", "message": None, "temp_password": None},
            )

    a.is_superadmin = want
    db.add(a)
    db.commit()
    return RedirectResponse("/superadmin", status_code=303)


@router.post("/superadmin/admins/toggle_disabled")
def superadmin_toggle_disabled(
    request: Request,
    admin_id: str = Form(...),
    disable: str = Form(...),  # "true" | "false"
    db: Session = Depends(get_db),
):
    redir = require_superadmin(request, db)
    if redir:
        return redir

    a = db.query(Admin).filter(Admin.id == admin_id).first()
    if not a:
        return RedirectResponse("/superadmin", status_code=303)

    want_disable = (disable == "true")

    if want_disable and a.is_superadmin and _superadmin_count(db) <= 1:
        return _templates(request).TemplateResponse(
            "superadmin.html",
            {"request": request, "admins": db.query(Admin).order_by(Admin.username.asc()).all(), "settings": get_settings(db),
             "error": "Cannot disable the last super admin.", "message": None, "temp_password": None},
        )

    a.is_disabled = want_disable
    db.add(a)
    db.commit()
    return RedirectResponse("/superadmin", status_code=303)


@router.post("/superadmin/admins/reset_password")
def superadmin_reset_password(
    request: Request,
    admin_id: str = Form(...),
    db: Session = Depends(get_db),
):
    redir = require_superadmin(request, db)
    if redir:
        return redir

    a = db.query(Admin).filter(Admin.id == admin_id).first()
    if not a:
        return RedirectResponse("/superadmin", status_code=303)

    temp_pw = _gen_temp_password(16)
    a.password_hash = argon2.hash(temp_pw)
    a.force_password_change = True
    db.add(a)
    db.commit()

    return _templates(request).TemplateResponse(
        "superadmin.html",
        {"request": request, "admins": db.query(Admin).order_by(Admin.username.asc()).all(), "settings": get_settings(db),
         "error": None, "message": f"Temporary password generated for {a.username}. Copy it now (shown once).",
         "temp_password": temp_pw},
    )
