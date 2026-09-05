from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.connection import Base
from app.database.models import DatasetUpload, Incident, IncidentEvent, MetricSnapshot, Trip
from app.services.detection import evaluate_operations


def test_reported_delay_overrides_timestamp_inference() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    scheduled = datetime(2026, 9, 4, 9, 0)

    with Session(engine) as session:
        upload = DatasetUpload(filename="test.csv", valid_rows=10, invalid_rows=0, skipped_rows=0)
        session.add(upload)
        session.flush()
        session.add_all(
            [
                Trip(
                    dataset_upload_id=upload.id,
                    trip_id=f"T{index}",
                    vendor_id="Vendor A",
                    route_id="R1",
                    shift_id="Morning",
                    employee_id=f"E{index}",
                    transport_mode="cab",
                    scheduled_arrival=scheduled,
                    actual_arrival=scheduled + timedelta(minutes=20),
                    reported_delay_minutes=10 if index == 0 else 0,
                    status="completed",
                    gps_available=True,
                )
                for index in range(10)
            ]
        )
        session.commit()

        evaluate_operations(session, upload.id, Settings(database_url="sqlite:///:memory:"))

        snapshot = session.scalar(select(MetricSnapshot))
        assert snapshot is not None
        assert snapshot.completed_trips == 10
        assert snapshot.delayed_trips == 1
        assert snapshot.ota_value == 90.0
        assert snapshot.average_delay_minutes == 10.0


def test_acknowledged_incident_reopens_after_material_deterioration() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    scheduled = datetime(2026, 9, 4, 9, 0)

    with Session(engine) as session:
        upload = DatasetUpload(filename="test.csv", valid_rows=10, invalid_rows=0, skipped_rows=0)
        session.add(upload)
        session.flush()
        session.add_all(
            [
                Trip(
                    dataset_upload_id=upload.id,
                    trip_id=f"T{index}",
                    vendor_id="Vendor A",
                    route_id="R1",
                    shift_id="Morning",
                    employee_id=f"E{index}",
                    transport_mode="cab",
                    scheduled_arrival=scheduled,
                    actual_arrival=scheduled + timedelta(minutes=10 if index < 2 else 2),
                    status="completed",
                    gps_available=True,
                )
                for index in range(10)
            ]
        )
        session.commit()

        settings = Settings(database_url="sqlite:///:memory:")
        first = evaluate_operations(session, upload.id, settings)

        assert first is not None
        assert first.current_value == 80.0
        assert first.severity == "high"
        first.status = "acknowledged"
        first.acknowledged_at = datetime.utcnow()
        first.acknowledged_value = first.current_value
        first.attention_required = False
        session.add_all(
            [
                Trip(
                    dataset_upload_id=upload.id,
                    trip_id=f"T{index}",
                    vendor_id="Vendor A",
                    route_id="R1",
                    shift_id="Morning",
                    employee_id=f"E{index}",
                    transport_mode="cab",
                    scheduled_arrival=scheduled,
                    actual_arrival=scheduled + timedelta(minutes=20),
                    status="completed",
                    gps_available=True,
                )
                for index in range(10, 20)
            ]
        )
        session.commit()

        reopened = evaluate_operations(session, upload.id, settings)

        assert reopened is not None
        assert reopened.id == first.id
        assert reopened.current_value == 40.0
        assert reopened.status == "reopened"
        assert reopened.attention_required is True
        assert reopened.notification_count == 2
        assert len(list(session.scalars(select(Incident)))) == 2
        event_types = list(session.scalars(select(IncidentEvent.event_type)))
        assert event_types.count("opened") == 2
        assert "reopened" in event_types