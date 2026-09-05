from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.database.models import DatasetUpload, SafetyAlert, Trip, TripFeedback
from app.main import app


def test_data_dashboards_filter_and_paginate_database_rows() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    scheduled = datetime(2026, 9, 5, 9, 0)

    with Session(engine) as session:
        upload = DatasetUpload(filename="dashboard.csv", valid_rows=2, invalid_rows=0, skipped_rows=0)
        session.add(upload)
        session.flush()
        session.add_all([
            Trip(
                dataset_upload_id=upload.id,
                trip_id="TRIP-ON-TIME",
                vendor_id="Vendor A",
                route_id="R1",
                shift_id="Morning",
                employee_id="E1",
                employee_count=2,
                office_id="North Office",
                no_show_count=0,
                transport_mode="CAB",
                scheduled_arrival=scheduled,
                actual_arrival=scheduled + timedelta(minutes=12),
                status="completed",
                gps_available=True,
                delay_reason="NODELAY",
                reported_delay_minutes=0,
                driver_non_compliance=False,
                cab_non_compliance=False,
            ),
            Trip(
                dataset_upload_id=upload.id,
                trip_id="TRIP-DELAYED",
                vendor_id="Vendor B",
                route_id="R2",
                shift_id="Evening",
                employee_id="E2",
                employee_count=3,
                office_id="South Office",
                no_show_count=1,
                transport_mode="CAB",
                scheduled_arrival=scheduled,
                actual_arrival=scheduled + timedelta(minutes=10),
                status="completed",
                gps_available=True,
                delay_reason="TRAFFIC",
                reported_delay_minutes=10,
                driver_non_compliance=True,
                cab_non_compliance=False,
            ),
        ])
        session.add_all([
            TripFeedback(
                trip_id="TRIP-ON-TIME",
                employee_id="E1",
                trip_type="LOGIN",
                trip_at=scheduled,
                route_rating=5,
                driver_rating=5,
                cab_rating=4,
                safety_rating=5,
                marshal_rating=4,
                created_at=scheduled,
            ),
            TripFeedback(
                trip_id="TRIP-DELAYED",
                employee_id="E2",
                trip_type="LOGOUT",
                trip_at=scheduled,
                route_rating=2,
                driver_rating=1,
                cab_rating=2,
                safety_rating=3,
                marshal_rating=2,
                created_at=scheduled,
            ),
            SafetyAlert(
                trip_id="TRIP-DELAYED",
                employee_id="E2",
                event_id="ALERT-1",
                event_type="SOS",
                started_at=scheduled,
                acknowledged_at=None,
                state="OPEN",
                severity="critical",
                source="mobile",
            ),
        ])
        session.commit()

    def test_database():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = test_database
    try:
        with TestClient(app) as client:
            trips = client.get("/api/dashboards/trips", params={"delayed": "true", "pageSize": 10})
            assert trips.status_code == 200
            assert trips.json()["summary"]["totalTrips"] == 1
            assert trips.json()["summary"]["delayedTrips"] == 1
            assert trips.json()["summary"]["affectedEmployees"] == 3
            assert trips.json()["rows"][0]["delayReason"] == "TRAFFIC"
            assert trips.json()["pagination"]["totalRows"] == 1
            trip_export = client.get("/api/dashboards/trips/export", params={"delayed": "true"})
            assert trip_export.status_code == 200
            assert "trips-filtered.csv" in trip_export.headers["content-disposition"]
            assert "TRIP-DELAYED" in trip_export.text
            assert "TRIP-ON-TIME" not in trip_export.text

            feedback = client.get("/api/dashboards/feedback", params={
                "ratingCategory": "driver",
                "maxRating": 2,
                "pageSize": 10,
            })
            assert feedback.status_code == 200
            assert feedback.json()["summary"]["totalResponses"] == 1
            assert feedback.json()["rows"][0]["vendorId"] == "Vendor B"

            alerts = client.get("/api/dashboards/safety-alerts", params={"state": "OPEN", "pageSize": 10})
            assert alerts.status_code == 200
            assert alerts.json()["summary"]["openAlerts"] == 1
            assert alerts.json()["rows"][0]["eventId"] == "ALERT-1"
            assert alerts.json()["rows"][0]["vendorId"] == "Vendor B"
    finally:
        app.dependency_overrides.clear()
