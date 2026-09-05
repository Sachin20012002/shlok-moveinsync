import json
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.database.models import DatasetUpload, Incident, Trip
from app.main import app
from app.services.detection import evaluate_operations
from app.core.config import Settings


def test_agent_streams_grounded_sse_without_mutating_incidents() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    scheduled = datetime(2026, 9, 5, 9, 0)

    with Session(engine) as session:
        upload = DatasetUpload(filename="agent-test.csv", valid_rows=10, invalid_rows=0, skipped_rows=0)
        session.add(upload)
        session.flush()
        session.add_all(
            [
                Trip(
                    dataset_upload_id=upload.id,
                    trip_id=f"AGENT-{index}",
                    vendor_id="Vendor A",
                    route_id="Route 1",
                    shift_id="Morning",
                    employee_id=f"EMP-{index}",
                    transport_mode="CAB",
                    scheduled_arrival=scheduled,
                    actual_arrival=scheduled + timedelta(minutes=12 if index < 3 else 2),
                    status="completed",
                    gps_available=True,
                )
                for index in range(10)
            ]
        )
        session.commit()
        evaluate_operations(session, upload.id, Settings(database_url="sqlite://"))

    def test_database():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = test_database
    try:
        with TestClient(app) as client:
            before = client.get("/api/incidents").json()
            response = client.post(
                "/api/agent/chat",
                json={"message": "Summarize current health", "history": []},
            )
            after = client.get("/api/incidents").json()

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.text.startswith("event: context\n")
        assert "event: token\n" in response.text
        assert "70.00%" in response.text
        assert response.text.rstrip().endswith('data: {"ok": true}')
        assert before == after

        incident_id = before[0]["id"]
        with TestClient(app) as client:
            scoped = client.post(
                "/api/agent/chat",
                json={
                    "message": "Explain this incident",
                    "history": [],
                    "incidentId": incident_id,
                },
            )
            missing = client.post(
                "/api/agent/chat",
                json={"message": "Explain this incident", "incidentId": 99999},
            )

        assert scoped.status_code == 200
        assert '"scope": "incident"' in scoped.text
        assert f'"incidentId": {incident_id}' in scoped.text
        scoped_answer = "".join(
            json.loads(line[6:])["content"]
            for line in scoped.text.splitlines()
            if line.startswith("data: ") and '"content"' in line
        )
        assert "Incident analysis:" in scoped_answer
        assert missing.status_code == 404
        assert missing.json()["detail"] == "Incident not found"
    finally:
        app.dependency_overrides.clear()
