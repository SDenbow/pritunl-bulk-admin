import io
from fastapi import HTTPException, APIRouter, Depends, Form, Request, Query
from fastapi.responses import RedirectResponse, Response, PlainTextResponse
from sqlalchemy.orm import Session
from passlib.hash import argon2
import qrcode
import pyotp

from ..bootstrap import is_bootstrapped
from ..db import get_db
from ..settings import settings
from ..crypto import encrypt_str, decrypt_str
from ..auth.models import Admin
from ..auth.totp import new_totp_secret, totp_now_ok


def setup_guard(token: str | None = None):
    # If already bootstrapped, setup must disappear completely
    if is_bootstrapped():
        raise HTTPException(status_code=404)

    # If SETUP_TOKEN is configured, enforce it
    if settings.setup_token:
        if token != settings.setup_token:
            raise HTTPException(status_code=404)

router = APIRouter(dependencies=[Depends(setup_guard)])
def _templates(request: Request):
    return request.app.state.templates


def _setup_allowed(db: Session) -> bool:
    return db.query(Admin).count() == 0


def _token_ok(token: str | None) -> bool:
    # If SETUP_TOKEN isn't set, allow (not recommended). Keep for dev friendliness.
    if not settings.setup_token:
        return True
    return token == settings.setup_token


@router.get("/setup")
def setup_get(
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if not _setup_allowed(db):
        return RedirectResponse(url="/login?msg=setup_complete", status_code=303)

    return _templates(request).TemplateResponse(
        "setup_admin.html",
        {"request": request, "error": None, "token": token or ""},
    )


@router.post("/setup")
def setup_post(
    request: Request,
    token: str | None = Query(default=None),
    username: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    enable_totp: str = Form(default=""),
    db: Session = Depends(get_db),
):
    if not _setup_allowed(db):
        return RedirectResponse(url="/login?msg=setup_complete", status_code=303)

    username = username.strip()
    if not username:
        return _templates(request).TemplateResponse(
            "setup_admin.html",
            {"request": request, "error": "Username is required.", "token": token or ""},
        )

    if password != password2:
        return _templates(request).TemplateResponse(
            "setup_admin.html",
            {"request": request, "error": "Passwords do not match.", "token": token or ""},
        )

    if len(password) < 12:
        return _templates(request).TemplateResponse(
            "setup_admin.html",
            {"request": request, "error": "Password must be at least 12 characters.", "token": token or ""},
        )

    totp_enabled = enable_totp == "on"

    admin = Admin(
        username=username,
        password_hash=argon2.hash(password),
        is_totp_enabled=totp_enabled,
        totp_secret_enc=None,
        is_superadmin=True,  # first admin must be superadmin
    )

    if totp_enabled:
        secret = new_totp_secret()
        admin.totp_secret_enc = encrypt_str(secret)

    db.add(admin)
    db.commit()

    if totp_enabled:
        return RedirectResponse(url=f"/setup/totp?token={token or ''}&u={username}", status_code=303)

    return RedirectResponse(url="/login?msg=setup_complete", status_code=303)


@router.get("/setup/totp")
def setup_totp_get(
    request: Request,
    token: str | None = Query(default=None),
    u: str = Query(...),
    db: Session = Depends(get_db),
):

    admin = db.query(Admin).filter(Admin.username == u).first()
    if not admin or not admin.is_totp_enabled or not admin.totp_secret_enc:
        return RedirectResponse(url="/login", status_code=303)

    secret = decrypt_str(admin.totp_secret_enc)
    issuer = "Pritunl Bulk Admin"
    uri = pyotp.TOTP(secret).provisioning_uri(name=admin.username, issuer_name=issuer)

    return _templates(request).TemplateResponse(
        "setup_totp.html",
        {
            "request": request,
            "error": None,
            "token": token or "",
            "username": admin.username,
            "secret": secret,
            "uri": uri,
        },
    )


@router.get("/setup/totp/qr.png")
def setup_totp_qr(
    token: str | None = Query(default=None),
    u: str = Query(...),
    db: Session = Depends(get_db),
):

    admin = db.query(Admin).filter(Admin.username == u).first()
    if not admin or not admin.is_totp_enabled or not admin.totp_secret_enc:
        return Response(status_code=404)

    secret = decrypt_str(admin.totp_secret_enc)
    issuer = "Pritunl Bulk Admin"
    uri = pyotp.TOTP(secret).provisioning_uri(name=admin.username, issuer_name=issuer)

    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@router.post("/setup/totp")
def setup_totp_post(
    request: Request,
    token: str | None = Query(default=None),
    u: str = Query(...),
    code: str = Form(...),
    db: Session = Depends(get_db),
):

    admin = db.query(Admin).filter(Admin.username == u).first()
    if not admin or not admin.is_totp_enabled or not admin.totp_secret_enc:
        return RedirectResponse(url="/login", status_code=303)

    secret = decrypt_str(admin.totp_secret_enc)
    if not totp_now_ok(secret, code.strip()):
        issuer = "Pritunl Bulk Admin"
        uri = pyotp.TOTP(secret).provisioning_uri(name=admin.username, issuer_name=issuer)
        return _templates(request).TemplateResponse(
            "setup_totp.html",
            {
                "request": request,
                "error": "Invalid code. Try again.",
                "token": token or "",
                "username": admin.username,
                "secret": secret,
                "uri": uri,
            },
        )

    return RedirectResponse(url="/login?msg=setup_complete", status_code=303)
