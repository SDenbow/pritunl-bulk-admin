from itsdangerous import URLSafeSerializer
from fastapi import Request
from ..settings import settings

_ser = URLSafeSerializer(settings.session_secret, salt="session")


def set_session(response, username: str):
    token = _ser.dumps({"u": username})
    # DEV-friendly: don't require HTTPS for cookie transmission.
    # In production you should set secure=True once you have trusted TLS.
    response.set_cookie("session", token, httponly=True, secure=False, samesite="lax")


def clear_session(response):
    response.delete_cookie("session")


def get_session_username(request: Request) -> str | None:
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        data = _ser.loads(token)
        return data.get("u")
    except Exception:
        return None
