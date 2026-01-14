import os
from pydantic import BaseModel


class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "prod")

    database_url: str = os.environ["DATABASE_URL"]
    session_secret: str = os.environ["SESSION_SECRET"]

    # Base64 urlsafe 32-byte key for Fernet
    master_key: str = os.environ["PRITUNL_UI_MASTER_KEY"]

    # Required for /setup before first admin exists
    setup_token: str | None = os.getenv("SETUP_TOKEN")

    allow_delete: bool = os.getenv("ALLOW_DELETE", "false").lower() == "true"


settings = Settings()
