from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.hash import argon2

from ..db import get_db, SessionLocal
from .models import Admin
from .session import set_session, clear_session, get_session_username
from ..crypto import decrypt_str
from .totp import totp_now_ok

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


@router.get("/login")
def login_page(request: Request, msg: str | None = Query(default=None)):
    message = "Setup complete. Please log in." if msg == "setup_complete" else None
    return _templates(request).TemplateResponse(
        "login.html",
        {"request": request, "error": None, "message": message},
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    totp: str = Form(default=""),
    db: Session = Depends(get_db),
):
    admin = db.query(Admin).filter(Admin.username == username.strip()).first()
    if not admin or not argon2.verify(password, admin.password_hash):
        return _templates(request).TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid credentials", "message": None},
        )

    if admin.is_disabled:
        return _templates(request).TemplateResponse(
            "login.html",
            {"request": request, "error": "Account disabled", "message": None},
        )

    if admin.is_totp_enabled:
        if not admin.totp_secret_enc:
            return _templates(request).TemplateResponse(
                "login.html",
                {"request": request, "error": "TOTP misconfigured", "message": None},
            )

        secret = decrypt_str(admin.totp_secret_enc)
        if not totp_now_ok(secret, totp.strip()):
            return _templates(request).TemplateResponse(
                "login.html",
                {"request": request, "error": "Invalid TOTP code", "message": None},
            )

    # If forced password change, log in but redirect to change password page
    if admin.force_password_change:
        resp = RedirectResponse(url="/me/change_password", status_code=303)
        set_session(resp, admin.username)
        return resp

    resp = RedirectResponse(url="/targets", status_code=303)
    set_session(resp, admin.username)
    return resp


@router.get("/me/change_password")
def change_password_get(request: Request, db: Session = Depends(get_db)):
    u = get_session_username(request)
    if not u:
        return RedirectResponse(url="/login", status_code=303)

    admin = db.query(Admin).filter(Admin.username == u).first()
    if not admin or admin.is_disabled:
        return RedirectResponse(url="/login", status_code=303)

    return _templates(request).TemplateResponse(
        "change_password.html",
        {"request": request, "error": None, "message": "Please set a new password." if admin.force_password_change else None},
    )


@router.post("/me/change_password")
def change_password_post(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password2: str = Form(...),
    db: Session = Depends(get_db),
):
    u = get_session_username(request)
    if not u:
        return RedirectResponse(url="/login", status_code=303)

    admin = db.query(Admin).filter(Admin.username == u).first()
    if not admin or admin.is_disabled:
        return RedirectResponse(url="/login", status_code=303)

    if not argon2.verify(current_password, admin.password_hash):
        return _templates(request).TemplateResponse(
            "change_password.html",
            {"request": request, "error": "Current password is incorrect", "message": None},
        )

    if new_password != new_password2:
        return _templates(request).TemplateResponse(
            "change_password.html",
            {"request": request, "error": "New passwords do not match", "message": None},
        )

    if len(new_password) < 12:
        return _templates(request).TemplateResponse(
            "change_password.html",
            {"request": request, "error": "Password must be at least 12 characters.", "message": None},
        )

    admin.password_hash = argon2.hash(new_password)
    admin.force_password_change = False
    db.add(admin)
    db.commit()

    return RedirectResponse(url="/targets", status_code=303)


@router.post("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    clear_session(resp)
    return resp


def require_login(request: Request) -> RedirectResponse | None:
    """
    Enforce:
      - session exists
      - admin exists and not disabled
      - if force_password_change, redirect to /me/change_password for all pages except allowed paths
    """
    u = get_session_username(request)
    if not u:
        return RedirectResponse(url="/login", status_code=303)

    path = request.url.path
    allowed = {"/login", "/logout", "/me/change_password"}

    db = SessionLocal()
    try:
        admin = db.query(Admin).filter(Admin.username == u).first()
        if not admin or admin.is_disabled:
            # clear session cookie on next response path
            return RedirectResponse(url="/login", status_code=303)

        if admin.force_password_change and path not in allowed:
            return RedirectResponse(url="/me/change_password", status_code=303)

    finally:
        db.close()

    return None
