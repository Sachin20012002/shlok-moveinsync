import csv
import io

from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import DatasetUpload, Incident, MetricSnapshot, Trip
from app.schemas.trip import TripRow
from app.services.detection import evaluate_dataset


REQUIRED_COLUMNS = set(TripRow.model_fields)


def ingest_csv(
    session: Session,
    filename: str,
    content: bytes,
    settings: Settings,
) -> tuple[DatasetUpload, bool]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV must be UTF-8 encoded") from error

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV header is missing")
    missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing_columns:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing_columns))}")

    valid_rows: list[TripRow] = []
    invalid_rows = 0
    skipped_rows = 0
    seen_trip_ids: set[str] = set()
    for raw_row in reader:
        if not any(value and value.strip() for value in raw_row.values() if value is not None):
            skipped_rows += 1
            continue
        try:
            row = TripRow.model_validate(raw_row)
            if row.trip_id in seen_trip_ids:
                skipped_rows += 1
                continue
            seen_trip_ids.add(row.trip_id)
            valid_rows.append(row)
        except ValidationError:
            invalid_rows += 1

    if not valid_rows:
        raise ValueError("CSV contains no valid trip rows")

    session.execute(delete(Incident))
    session.execute(delete(MetricSnapshot))
    session.execute(delete(Trip))
    session.execute(delete(DatasetUpload))
    upload = DatasetUpload(
        filename=filename,
        valid_rows=len(valid_rows),
        invalid_rows=invalid_rows,
        skipped_rows=skipped_rows,
    )
    session.add(upload)
    session.flush()
    session.add_all(
        [
            Trip(dataset_upload_id=upload.id, **row.model_dump())
            for row in valid_rows
        ]
    )
    session.commit()
    incident = evaluate_dataset(session, upload.id, settings)
    return upload, incident is not None