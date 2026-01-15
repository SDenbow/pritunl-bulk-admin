from fastapi import FastAPI
from starlette.templating import Jinja2Templates

from .settings import settings
from .db import Base, engine

# Ensure models are imported before create_all
from .auth import models as _auth_models  # noqa: F401
from .targets import models as _targets_models  # noqa: F401
from .importer import models as _import_models  # noqa: F401

from .setup.routes import router as setup_router
from .auth.routes import router as auth_router
from .targets.routes import router as targets_router


def create_app() -> FastAPI:
    if not settings.master_key:
        raise RuntimeError("PRITUNL_UI_MASTER_KEY must be set")

    app = FastAPI()

    Base.metadata.create_all(bind=engine)

    app.state.templates = Jinja2Templates(directory="app/templates")

    app.include_router(setup_router)
    app.include_router(auth_router)
    app.include_router(targets_router)

    return app


app = create_app()
