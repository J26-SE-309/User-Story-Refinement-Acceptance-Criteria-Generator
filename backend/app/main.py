"""FastAPI application for the User Story Refinement and Acceptance Criteria Generator."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health
from app.api.v1 import routes
from app.config import get_settings
from app.services.story_model import load_model


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        load_model()
        yield

    app = FastAPI(
        title="User Story Refinement and Acceptance Criteria Generator API",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(routes.router, prefix="/api/v1")
    return app


app = create_app()
