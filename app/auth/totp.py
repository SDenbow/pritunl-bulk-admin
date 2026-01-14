import pyotp


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_now_ok(secret: str, code: str) -> bool:
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    except Exception:
        return False
