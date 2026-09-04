from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.main import app


def test_upload_to_acknowledgment_flow() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def test_database():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = test_database
    sample_path = Path(__file__).parents[2] / "sample-data" / "ota-breach-demo.csv"

    try:
        with TestClient(app) as client, sample_path.open("rb") as sample:
            upload_response = client.post(
                "/api/datasets/upload",
                files={"file": (sample_path.name, sample, "text/csv")},
            )
            assert upload_response.status_code == 201
            assert upload_response.json()["incidentCreated"] is True

            dashboard = client.get("/api/dashboard").json()
            assert dashboard["onTimeArrival"]["value"] == 75.0
            assert dashboard["activeIncidentCount"] == 1

            incidents = client.get("/api/incidents").json()
            assert len(incidents) == 1
            assert incidents[0]["severity"] == "critical"

            acknowledged = client.post(
                f"/api/incidents/{incidents[0]['id']}/acknowledge"
            ).json()
            assert acknowledged["status"] == "acknowledged"
            assert client.get("/api/dashboard").json()["activeIncidentCount"] == 0
    finally:
        app.dependency_overrides.clear()