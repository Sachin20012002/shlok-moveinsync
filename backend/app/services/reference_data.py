import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.database.models import SafetyAlert, Trip, TripFeedback


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
    if not directory:
        return {"enrichedTrips": 0, "alerts": 0, "feedback": 0}
    data_dir = Path(directory).resolve()
    if not data_dir.is_dir():
        return {"enrichedTrips": 0, "alerts": 0, "feedback": 0}

    trip_ids = dict(session.execute(select(Trip.trip_id, Trip.id)).all())
    if not trip_ids:
        return {"enrichedTrips": 0, "alerts": 0, "feedback": 0}
    result = {
        "enrichedTrips": _enrich_trips(session, data_dir, trip_ids),
        "alerts": _import_alerts(session, data_dir, set(trip_ids)),
        "feedback": _import_feedback(session, data_dir, set(trip_ids)),
    }
    session.commit()
    return result
