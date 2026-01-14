from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.hash import argon2

from ..db import get_db
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

    resp = RedirectResponse(url="/targets", status_code=303)
    set_session(resp, admin.username)
    return resp


@router.post("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    clear_session(resp)
    return resp


def require_login(request: Request) -> RedirectResponse | None:
    if not get_session_username(request):
        return RedirectResponse(url="/login", status_code=303)
    return None
