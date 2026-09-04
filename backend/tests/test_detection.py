from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.connection import Base
from app.database.models import DatasetUpload, Incident, Trip
from app.services.detection import evaluate_dataset


def test_sla_breach_creates_only_one_open_incident() -> None:
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
        first = evaluate_dataset(session, upload.id, settings)
        second = evaluate_dataset(session, upload.id, settings)

        assert first is not None
        assert first.current_value == 80.0
        assert first.severity == "high"
        assert second is not None
        assert len(list(session.scalars(select(Incident)))) == 1