from sqlalchemy.orm import Session
from .settings_db import AppSettings


def get_settings(db: Session) -> AppSettings:
    s = db.query(AppSettings).filter(AppSettings.id == "global").first()
    if not s:
        s = AppSettings(id="global")
        db.add(s)
        db.commit()
        db.refresh(s)
    return s
