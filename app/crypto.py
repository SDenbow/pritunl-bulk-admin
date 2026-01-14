from cryptography.fernet import Fernet
from .settings import settings


def _fernet() -> Fernet:
    return Fernet(settings.master_key.encode())


def encrypt_str(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_str(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
