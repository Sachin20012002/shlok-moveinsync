import csv
import io
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.database.models import DatasetUpload, Incident, Trip
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
            assert dashboard["activeIncidentCount"] == 3

            operations = client.get("/api/operations")
            assert operations.status_code == 200
            operations_data = operations.json()
            assert operations_data["maximumDelayMinutes"] == 22.0
            assert operations_data["tripExceptions"][0]["tripId"] == "TRIP-007"
            incidents_by_title = {
                incident["title"]: incident["id"]
                for incident in client.get("/api/incidents").json()
            }
            assert incidents_by_title["On-time arrival below SLA"] in operations_data["tripExceptions"][0]["relatedIncidentIds"]
            gps_exception = next(
                trip for trip in operations_data["tripExceptions"]
                if "GPS unavailable" in trip["issue"]
            )
            assert incidents_by_title["GPS availability below target"] in gps_exception["relatedIncidentIds"]
            assert operations_data["shiftReadiness"][0]["status"] == "at_risk"
            assert operations_data["vendorWatchlist"][0]["vendorId"] == "Vendor A"
            assert operations_data["dataQuality"]["missingGps"] == 1
            assert len(operations_data["recommendedActions"]) == 3
            assert len(operations_data["timeline"]) == 3

            incidents = client.get("/api/incidents").json()
            assert len(incidents) == 3
            assert {incident["title"] for incident in incidents} == {
                "On-time arrival below SLA",
                "Vendor A on-time arrival below SLA",
                "GPS availability below target",
            }
            overall_incident = next(
                incident for incident in incidents
                if incident["title"] == "On-time arrival below SLA"
            )
            assert overall_incident["severity"] == "critical"

            acknowledged = client.post(
                f"/api/incidents/{overall_incident['id']}/acknowledge"
            ).json()
            assert acknowledged["status"] == "acknowledged"
            assert client.get("/api/dashboard").json()["activeIncidentCount"] == 2
    finally:
        app.dependency_overrides.clear()


def test_uploads_append_data_and_create_incidents_per_dataset() -> None:
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
    first_csv = sample_path.read_text(encoding="utf-8")
    second_csv = first_csv.replace("TRIP-0", "TRIP-1")

    try:
        with TestClient(app) as client:
            first = client.post(
                "/api/datasets/upload",
                files={"file": ("day-one.csv", first_csv, "text/csv")},
            )
            second = client.post(
                "/api/datasets/upload",
                files={"file": ("day-two.csv", second_csv, "text/csv")},
            )

            assert first.status_code == 201
            assert second.status_code == 201
            assert len(client.get("/api/incidents").json()) == 3

        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(DatasetUpload)) == 2
            assert session.scalar(select(func.count()).select_from(Trip)) == 24
            assert session.scalar(select(func.count()).select_from(Incident)) == 3
    finally:
        app.dependency_overrides.clear()


def test_upload_rejects_existing_trip_ids_without_deleting_data() -> None:
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
    sample_csv = sample_path.read_text(encoding="utf-8")

    try:
        with TestClient(app) as client:
            first = client.post(
                "/api/datasets/upload",
                files={"file": ("first.csv", sample_csv, "text/csv")},
            )
            duplicate = client.post(
                "/api/datasets/upload",
                files={"file": ("duplicate.csv", sample_csv, "text/csv")},
            )

            assert first.status_code == 201
            assert duplicate.status_code == 422
            assert "Trip IDs already exist" in duplicate.json()["detail"]

        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(DatasetUpload)) == 1
            assert session.scalar(select(func.count()).select_from(Trip)) == 12
            assert session.scalar(select(func.count()).select_from(Incident)) == 3
    finally:
        app.dependency_overrides.clear()


def test_acknowledged_incident_reopens_and_can_be_acknowledged_again() -> None:
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
    initial_csv = sample_path.read_text(encoding="utf-8")
    source_rows = list(csv.DictReader(io.StringIO(initial_csv)))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=source_rows[0].keys(), lineterminator="\n")
    writer.writeheader()
    for index, row in enumerate(source_rows, start=201):
        row["trip_id"] = f"TRIP-{index}"
        row["scheduled_arrival"] = "2026-09-05T09:00:00"
        row["actual_arrival"] = "2026-09-05T09:30:00"
        row["gps_available"] = "true"
        writer.writerow(row)

    try:
        with TestClient(app) as client:
            client.post(
                "/api/datasets/upload",
                files={"file": ("initial.csv", initial_csv, "text/csv")},
            )
            overall = next(
                incident for incident in client.get("/api/incidents").json()
                if incident["title"] == "On-time arrival below SLA"
            )
            incident_id = overall["id"]
            acknowledged = client.post(
                f"/api/incidents/{incident_id}/acknowledge"
            ).json()
            assert acknowledged["acknowledgedValue"] == 75.0

            client.post(
                "/api/datasets/upload",
                files={"file": ("deterioration.csv", output.getvalue(), "text/csv")},
            )
            reopened = client.get(f"/api/incidents/{incident_id}").json()
            assert reopened["id"] == incident_id
            assert reopened["status"] == "reopened"
            assert reopened["currentValue"] == 37.5
            assert reopened["attentionRequired"] is True
            assert reopened["notificationCount"] == 2

            events = client.get(f"/api/incidents/{incident_id}/events").json()
            assert [event["eventType"] for event in events] == [
                "opened",
                "acknowledged",
                "reopened",
            ]

            reacknowledged = client.post(
                f"/api/incidents/{incident_id}/acknowledge"
            ).json()
            assert reacknowledged["status"] == "acknowledged"
            assert reacknowledged["acknowledgedValue"] == 37.5
            assert reacknowledged["attentionRequired"] is False
    finally:
        app.dependency_overrides.clear()