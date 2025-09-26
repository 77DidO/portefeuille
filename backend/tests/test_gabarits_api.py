from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api import gabarits as gabarits_api
from app.models.base import Base
from app.models.gabarits import Gabarit


def _create_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    return engine, TestingSessionLocal


def _create_app(SessionLocal):
    app = FastAPI()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.include_router(gabarits_api.router)
    app.dependency_overrides[deps.get_db] = override_get_db
    return app


def test_gabarits_crud_flow() -> None:
    engine, SessionLocal = _create_session()
    try:
        app = _create_app(SessionLocal)
        client = TestClient(app)

        response = client.post(
            "/gabarits/",
            json={
                "nom": "Rapport Mensuel",
                "description": "Synthèse des performances",
                "contenu": "Contenu du rapport",
                "metadonnees": {"version": 1},
            },
        )
        assert response.status_code == 201
        gabarit = response.json()
        assert gabarit["nom"] == "Rapport Mensuel"
        gabarit_id = gabarit["id"]

        # Attempt to create a duplicate name
        response = client.post(
            "/gabarits/",
            json={
                "nom": "Rapport Mensuel",
                "description": "Doublon",
                "contenu": "Autre contenu",
            },
        )
        assert response.status_code == 400

        response = client.get("/gabarits/")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == gabarit_id

        response = client.get(f"/gabarits/{gabarit_id}")
        assert response.status_code == 200
        assert response.json()["contenu"] == "Contenu du rapport"

        response = client.patch(
            f"/gabarits/{gabarit_id}",
            json={
                "description": "Synthèse mise à jour",
                "metadonnees": {"version": 2},
            },
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["description"] == "Synthèse mise à jour"
        assert updated["metadonnees"] == {"version": 2}

        response = client.delete(f"/gabarits/{gabarit_id}")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        response = client.get(f"/gabarits/{gabarit_id}")
        assert response.status_code == 404
    finally:
        engine.dispose()


def test_update_gabarit_requires_unique_name() -> None:
    engine, SessionLocal = _create_session()
    db = SessionLocal()
    try:
        db.add_all(
            [
                Gabarit(
                    nom="Rapport 1",
                    description=None,
                    contenu="Contenu 1",
                    metadonnees=None,
                ),
                Gabarit(
                    nom="Rapport 2",
                    description=None,
                    contenu="Contenu 2",
                    metadonnees=None,
                ),
            ]
        )
        db.commit()
        db.close()

        app = _create_app(SessionLocal)
        client = TestClient(app)

        response = client.patch(
            "/gabarits/1",
            json={"nom": "Rapport 2"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Un gabarit avec ce nom existe déjà"
    finally:
        engine.dispose()
