from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.connection import Base
from app.database.models import DatasetUpload, Incident, Trip
from app.services.operations_analytics import get_incident_trip_evidence, get_operations_analytics


def test_date_scoped_analytics_and_incident_evidence() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    settings = Settings(database_url="sqlite:///:memory:")

    with Session(engine) as session:
        upload = DatasetUpload(filename="test.csv", valid_rows=4, invalid_rows=0, skipped_rows=0)
        session.add(upload)
        session.flush()
        scheduled_dates = [
            datetime(2026, 7, 1, 9),
            datetime(2026, 7, 2, 9),
            datetime(2026, 7, 8, 9),
            datetime(2026, 8, 1, 9),
        ]
        delays = [10.0, 0.0, 0.0, 20.0]
        vendors = ["Vendor A", "Vendor A", "Vendor B", "Vendor B"]
        for index, scheduled in enumerate(scheduled_dates):
            session.add(Trip(
                dataset_upload_id=upload.id,
                trip_id=f"T{index}",
                vendor_id=vendors[index],
                route_id="R1",
                shift_id="Morning" if index < 2 else "Evening",
                employee_id=f"E{index}",
                employee_count=index + 1,
                transport_mode="cab",
                scheduled_arrival=scheduled,
                actual_arrival=scheduled + timedelta(minutes=20),
                reported_delay_minutes=delays[index],
                delay_reason="Traffic" if delays[index] else None,
                status="completed",
                gps_available=True,
            ))
        incident = Incident(
            incident_type="vendor_ota_below_sla:Vendor A",
            title="Vendor A below SLA",
            severity="high",
            current_value=50,
            sla_value=90,
            affected_employees=1,
            contributing_vendor="Vendor A",
            reason="OTA below SLA",
            recommended_action="Review delayed trips",
        )
        session.add(incident)
        session.commit()

        analytics = get_operations_analytics(session, settings, date(2026, 7, 1), date(2026, 7, 8))
        assert analytics["availableRange"] == {"startDate": "2026-07-01", "endDate": "2026-08-01"}
        assert analytics["summary"] == {
            "completedTrips": 3,
            "delayedTrips": 1,
            "ota": 66.67,
            "affectedEmployees": 1,
            "averageDelayMinutes": 10.0,
        }
        assert len(analytics["weeklyTrend"]) == 2
        assert analytics["weeklyTrend"][1]["changePoints"] == 50.0

        evidence = get_incident_trip_evidence(session, settings, incident.id, page=1, page_size=10)
        assert evidence is not None
        assert evidence["totalTrips"] == 1
        assert evidence["page"] == 1
        assert evidence["pageSize"] == 10
        assert evidence["totalPages"] == 1
        assert evidence["trips"][0]["tripId"] == "T0"