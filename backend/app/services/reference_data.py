import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import MetaData, Table, func, inspect, insert, select, text
from sqlalchemy.orm import Session

from app.database.models import DatasetUpload, SafetyAlert, Trip, TripFeedback


BATCH_SIZE = 2_000
TIMESTAMP_FORMAT = "%B %d, %Y, %I:%M %p"


def _identifier(value: str | None) -> str:
    return (value or "").strip().replace(",", "")


def _optional_text(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _boolean(value: str | None) -> bool | None:
    cleaned = (value or "").strip().lower()
    if not cleaned:
        return None
    if cleaned in {"true", "1", "yes"}:
        return True
    if cleaned in {"false", "0", "no"}:
        return False
    return None


def _timestamp(value: str | None) -> datetime | None:
    cleaned = (value or "").strip()
    return datetime.strptime(cleaned, TIMESTAMP_FORMAT) if cleaned else None


def _flush(session: Session, model: type, rows: list[dict[str, object]]) -> None:
    if rows:
        session.execute(insert(model), rows)
        rows.clear()


def _epoch(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)


def _source_table(session: Session, name: str) -> Table | None:
    bind = session.get_bind()
    if name not in inspect(bind).get_table_names():
        return None
    return Table(name, MetaData(), autoload_with=bind)


def _import_database_trips(session: Session) -> int:
    if session.scalar(select(func.count()).select_from(Trip)):
        return 0
    source = _source_table(session, "trips")
    if source is None or "trip_date" not in source.c or "planned_end_epoch" not in source.c:
        return 0

    total = session.scalar(select(func.count()).select_from(source)) or 0
    upload = DatasetUpload(
        filename="Cloud PostgreSQL trips",
        valid_rows=total,
        invalid_rows=0,
        skipped_rows=0,
    )
    session.add(upload)
    session.flush()
    imported = 0
    pending: list[dict[str, object]] = []
    rows = session.execute(select(source)).mappings().yield_per(BATCH_SIZE)
    for row in rows:
        scheduled_arrival = _epoch(row["planned_end_epoch"])
        if scheduled_arrival is None:
            continue
        actual_arrival = _epoch(row["actual_end_epoch"])
        trip_id = str(row["trip_id"])
        pending.append({
            "dataset_upload_id": upload.id,
            "trip_id": trip_id,
            "vendor_id": row["vendor_id"],
            "route_id": "Unavailable",
            "shift_id": row["shift_type"],
            "employee_id": f"aggregate:{trip_id}",
            "employee_count": row["actual_employee_count"] or 0,
            "office_id": row["office"],
            "no_show_count": row["no_show_count"] or 0,
            "transport_mode": row["product_type"],
            "scheduled_arrival": scheduled_arrival,
            "actual_arrival": actual_arrival,
            "status": "completed" if actual_arrival is not None else "in_progress",
            "cost": None,
            "distance_km": row["traveled_km"],
            "rating": None,
            "gps_available": None,
            "delay_reason": row["delay_reason"],
            "reported_delay_minutes": row["delay_minutes"],
            "driver_non_compliance": row["is_driver_nc"],
            "cab_non_compliance": row["is_cab_nc"],
        })
        imported += 1
        if len(pending) >= BATCH_SIZE:
            _flush(session, Trip, pending)
    _flush(session, Trip, pending)
    upload.valid_rows = imported
    session.flush()
    return imported


def _backfill_database_delays(session: Session) -> int:
    source = _source_table(session, "trips")
    if source is None or "delay_minutes" not in source.c:
        return 0
    result = session.execute(text(
        "UPDATE shlok_trips AS target "
        "SET reported_delay_minutes = source.delay_minutes "
        "FROM trips AS source "
        "WHERE target.trip_id = CAST(source.trip_id AS VARCHAR) "
        "AND target.reported_delay_minutes IS NULL"
    ))
    return result.rowcount


def _import_database_alerts(session: Session, trip_ids: set[str]) -> int:
    if session.scalar(select(func.count()).select_from(SafetyAlert)):
        return 0
    source = _source_table(session, "alerts")
    if source is None:
        return 0
    imported = 0
    pending: list[dict[str, object]] = []
    for row in session.execute(select(source)).mappings().yield_per(BATCH_SIZE):
        trip_id = str(row["trip_id"])
        if trip_id not in trip_ids:
            continue
        severity = str(row["severity"]) if row["severity"] is not None else None
        pending.append({
            "trip_id": trip_id,
            "employee_id": str(row["stwid"]) if row["stwid"] is not None else None,
            "event_id": str(row["event_id"]),
            "event_type": row["event_type"],
            "started_at": row["start_time"],
            "acknowledged_at": row["acknowledge_time"],
            "state": row["state_text"],
            "severity": None if severity == "False" else severity,
            "source": row["source"],
        })
        imported += 1
        if len(pending) >= BATCH_SIZE:
            _flush(session, SafetyAlert, pending)
    _flush(session, SafetyAlert, pending)
    return imported


def _import_database_feedback(session: Session, trip_ids: set[str]) -> int:
    if session.scalar(select(func.count()).select_from(TripFeedback)):
        return 0
    source = _source_table(session, "trip_feedback")
    if source is None or "stwid" not in source.c:
        return 0
    imported = 0
    pending: list[dict[str, object]] = []
    for row in session.execute(select(source)).mappings().yield_per(BATCH_SIZE):
        trip_id = str(row["trip_id"])
        if trip_id not in trip_ids:
            continue
        pending.append({
            "trip_id": trip_id,
            "employee_id": str(row["stwid"]) if row["stwid"] is not None else None,
            "trip_type": row["trip_type"],
            "trip_at": row["trip_at"],
            "route_rating": row["route_rating"],
            "driver_rating": row["driver_rating"],
            "cab_rating": row["cab_rating"],
            "safety_rating": row["safety_rating"],
            "marshal_rating": row["marshal_rating"],
            "created_at": row["creation_time"],
        })
        imported += 1
        if len(pending) >= BATCH_SIZE:
            _flush(session, TripFeedback, pending)
    _flush(session, TripFeedback, pending)
    return imported


def _enrich_trips(session: Session, data_dir: Path, trip_ids: dict[str, int]) -> int:
    needs_enrichment = session.scalar(
        select(func.count()).select_from(Trip).where(Trip.office_id.is_(None))
    ) or 0
    if not needs_enrichment:
        return 0

    updated = 0
    pending: list[dict[str, object]] = []
    for path in sorted(data_dir.glob("Ride_data _trip-*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                database_id = trip_ids.get(_identifier(row.get("trip_id")))
                if database_id is None:
                    continue
                pending.append({
                    "id": database_id,
                    "office_id": _optional_text(row.get("office")),
                    "no_show_count": int((row.get("noshow_cnt") or "0").replace(",", "")),
                    "delay_reason": _optional_text(row.get("delay_reason")),
                    "driver_non_compliance": _boolean(row.get("is_driver_nc")),
                    "cab_non_compliance": _boolean(row.get("is_cab_nc")),
                })
                updated += 1
                if len(pending) >= BATCH_SIZE:
                    session.bulk_update_mappings(Trip, pending)
                    pending.clear()
    if pending:
        session.bulk_update_mappings(Trip, pending)
    return updated


def _import_alerts(session: Session, data_dir: Path, trip_ids: set[str]) -> int:
    if session.scalar(select(func.count()).select_from(SafetyAlert)):
        return 0
    path = data_dir / "alerts_data.csv"
    if not path.exists():
        return 0
    imported = 0
    pending: list[dict[str, object]] = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            trip_id = _identifier(row.get("trip_id"))
            started_at = _timestamp(row.get("start_time"))
            if trip_id not in trip_ids or started_at is None:
                continue
            severity = _optional_text(row.get("severity"))
            pending.append({
                "trip_id": trip_id,
                "employee_id": _identifier(row.get("stwid")) or None,
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "started_at": started_at,
                "acknowledged_at": _timestamp(row.get("acknowledge_time")),
                "state": row["state_text"],
                "severity": None if severity == "False" else severity,
                "source": _optional_text(row.get("source")),
            })
            imported += 1
            if len(pending) >= BATCH_SIZE:
                _flush(session, SafetyAlert, pending)
    _flush(session, SafetyAlert, pending)
    return imported


def _import_feedback(session: Session, data_dir: Path, trip_ids: set[str]) -> int:
    if session.scalar(select(func.count()).select_from(TripFeedback)):
        return 0
    path = data_dir / "trip_feedback.csv"
    if not path.exists():
        return 0
    imported = 0
    pending: list[dict[str, object]] = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            trip_id = _identifier(row.get("trip_id"))
            trip_at = _timestamp(row.get("trip_date"))
            created_at = _timestamp(row.get("creation_time"))
            if trip_id not in trip_ids or trip_at is None or created_at is None:
                continue
            pending.append({
                "trip_id": trip_id,
                "employee_id": _identifier(row.get("stwid")) or None,
                "trip_type": row["trip_type"],
                "trip_at": trip_at,
                "route_rating": int(row["route_rating"]),
                "driver_rating": int(row["driver_rating"]),
                "cab_rating": int(row["cab_rating"]),
                "safety_rating": int(row["safety_rating"]),
                "marshal_rating": int(row["marshal_rating"]),
                "created_at": created_at,
            })
            imported += 1
            if len(pending) >= BATCH_SIZE:
                _flush(session, TripFeedback, pending)
    _flush(session, TripFeedback, pending)
    return imported


def sync_reference_data(session: Session, directory: str | None) -> dict[str, int]:
    imported_trips = _import_database_trips(session)
    trip_ids = dict(session.execute(select(Trip.trip_id, Trip.id)).all())
    if not trip_ids:
        return {"importedTrips": 0, "enrichedTrips": 0, "alerts": 0, "feedback": 0}
    data_dir = Path(directory).resolve() if directory else None
    has_csv_data = data_dir is not None and data_dir.is_dir()
    result = {
        "importedTrips": imported_trips,
        "enrichedTrips": _enrich_trips(session, data_dir, trip_ids) if has_csv_data else 0,
        "backfilledDelays": _backfill_database_delays(session),
        "alerts": _import_database_alerts(session, set(trip_ids)),
        "feedback": _import_database_feedback(session, set(trip_ids)),
    }
    if has_csv_data:
        result["alerts"] += _import_alerts(session, data_dir, set(trip_ids))
        result["feedback"] += _import_feedback(session, data_dir, set(trip_ids))
    session.commit()
    return result
