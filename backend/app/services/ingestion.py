import csv
import io
from datetime import datetime, timezone
from typing import BinaryIO

from pydantic import ValidationError
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import DatasetUpload, Trip
from app.schemas.trip import TripRow
from app.services.detection import evaluate_dataset


REQUIRED_COLUMNS = {
    name for name, field in TripRow.model_fields.items() if field.is_required()
}
MOVEINSYNC_COLUMNS = {
    "trip_id",
    "vendor_id",
    "product_type",
    "shift_type",
    "planned_end_epoch",
    "actual_end_epoch",
    "traveled_km",
    "actualemployee_cnt",
}
BATCH_SIZE = 2_000


def _number(value: str) -> float | None:
    cleaned = value.strip().replace(",", "")
    return float(cleaned) if cleaned else None


def _epoch(value: str) -> datetime | None:
    numeric = _number(value)
    if numeric is None:
        return None
    return datetime.fromtimestamp(numeric, tz=timezone.utc).replace(tzinfo=None)


def _moveinsync_trip(raw_row: dict[str, str | None]) -> TripRow:
    trip_id = (raw_row.get("trip_id") or "").strip().replace(",", "")
    actual_arrival = _epoch(raw_row.get("actual_end_epoch") or "")
    employee_count = int(_number(raw_row.get("actualemployee_cnt") or "") or 0)
    return TripRow(
        trip_id=trip_id,
        vendor_id=raw_row.get("vendor_id") or "",
        route_id="Unavailable",
        shift_id=raw_row.get("shift_type") or "Unscheduled",
        employee_id=f"aggregate:{trip_id}",
        employee_count=employee_count,
        transport_mode=raw_row.get("product_type") or "Unknown",
        scheduled_arrival=_epoch(raw_row.get("planned_end_epoch") or ""),
        actual_arrival=actual_arrival,
        status="completed" if actual_arrival is not None else "in_progress",
        distance_km=_number(raw_row.get("traveled_km") or ""),
        gps_available=None,
    )


def _existing_trip_ids(session: Session, trip_ids: list[str]) -> set[str]:
    existing: set[str] = set()
    for start in range(0, len(trip_ids), BATCH_SIZE):
        existing.update(
            session.scalars(
                select(Trip.trip_id).where(
                    Trip.trip_id.in_(trip_ids[start:start + BATCH_SIZE])
                )
            )
        )
    return existing


def ingest_csv(
    session: Session,
    filename: str,
    content: bytes | BinaryIO,
    settings: Settings,
) -> tuple[DatasetUpload, bool]:
    wrapped_stream: io.TextIOWrapper | None = None
    if isinstance(content, bytes):
        try:
            stream = io.StringIO(content.decode("utf-8-sig"))
        except UnicodeDecodeError as error:
            raise ValueError("CSV must be UTF-8 encoded") from error
    else:
        content.seek(0)
        wrapped_stream = io.TextIOWrapper(content, encoding="utf-8-sig", newline="")
        stream = wrapped_stream

    reader = csv.DictReader(stream)
    if reader.fieldnames is None:
        raise ValueError("CSV header is missing")
    columns = set(reader.fieldnames)
    is_moveinsync = MOVEINSYNC_COLUMNS <= columns
    missing_columns = set() if is_moveinsync else REQUIRED_COLUMNS - columns
    if missing_columns:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing_columns))}")

    upload = DatasetUpload(
        filename=filename,
        valid_rows=0,
        invalid_rows=0,
        skipped_rows=0,
    )
    session.add(upload)
    session.flush()

    valid_rows = 0
    invalid_rows = 0
    skipped_rows = 0
    seen_trip_ids: set[str] = set()
    pending: list[dict[str, object]] = []

    def flush_pending() -> None:
        if not pending:
            return
        trip_ids = [str(row["trip_id"]) for row in pending]
        existing_trip_ids = _existing_trip_ids(session, trip_ids)
        if existing_trip_ids:
            examples = ", ".join(sorted(existing_trip_ids)[:3])
            raise ValueError(
                f"Trip IDs already exist: {examples}. Use unique trip_id values for each upload."
            )
        session.execute(insert(Trip), pending)
        pending.clear()

    for raw_row in reader:
        if not any(value and value.strip() for value in raw_row.values() if value is not None):
            skipped_rows += 1
            continue
        try:
            row = _moveinsync_trip(raw_row) if is_moveinsync else TripRow.model_validate(raw_row)
            if row.trip_id in seen_trip_ids:
                skipped_rows += 1
                continue
            seen_trip_ids.add(row.trip_id)
            pending.append({"dataset_upload_id": upload.id, **row.model_dump()})
            valid_rows += 1
            if len(pending) >= BATCH_SIZE:
                flush_pending()
        except (TypeError, ValueError, ValidationError, OSError, OverflowError):
            invalid_rows += 1

    flush_pending()
    if wrapped_stream is not None:
        wrapped_stream.detach()

    if not valid_rows:
        raise ValueError("CSV contains no valid trip rows")
    upload.valid_rows = valid_rows
    upload.invalid_rows = invalid_rows
    upload.skipped_rows = skipped_rows
    session.commit()
    incident = evaluate_dataset(session, upload.id, settings)
    return upload, incident is not None