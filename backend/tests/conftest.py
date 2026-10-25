import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import db, models
from app.main import create_app


@pytest.fixture
def test_session_factory():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(test_engine)
    test_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with test_session() as session:
        session.add_all(
            [
                models.ValidatedRequirement(
                    id=requirement_id,
                    text="A learner can book a tutor.",
                    validation_status="validated",
                )
                for requirement_id in ("REQ-1", "REQ-EDIT", "REQ-2", "REQ-3")
            ]
        )
        session.commit()

    return test_session


@pytest.fixture
def client(monkeypatch, test_session_factory):
    monkeypatch.setattr(db, "database_ok", lambda: False)
    # Keep API persistence/contract tests independent of heavyweight model files.
    from app.services.generation import generate_baseline
    monkeypatch.setattr("app.api.v1.routes.generate_refinement", generate_baseline)
    app = create_app()

    def override_session():
        with test_session_factory() as session:
            yield session

    app.dependency_overrides[db.get_session] = override_session
    return TestClient(app)
