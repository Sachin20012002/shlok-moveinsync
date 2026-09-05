from __future__ import annotations

import argparse
import csv
import os
import sys
from collections.abc import Callable, Iterable, Iterator
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg


TRIP_FILES = (
    "Ride_data _trip-may_2026.csv",
    "Ride_data _trip-June_2026.csv",
    "Ride_data _trip-July_2026.csv",
)
ALERT_FILE = "alerts_data.csv"
BILL_FILE = "bill_data.csv"
EMPLOYEE_FILE = "emp_Data.csv"
FEEDBACK_FILE = "trip_feedback.csv"

TRIP_COLUMNS = (
    "trip_id", "business_unit", "office", "product_type", "trip_date", "shift_type",
    "trip_direction", "actual_escort", "vendor_id", "planned_cab_registration",
    "actual_cab_registration", "actual_cab_capacity", "planned_km", "traveled_km",
    "planned_start_epoch", "planned_end_epoch", "actual_start_epoch", "actual_end_epoch",
    "delay_reason", "delay_minutes", "route_source", "actual_cab_fuel_type",
    "is_driver_nc", "is_cab_nc", "trip_nodal", "planned_employee_count",
    "actual_employee_count", "no_show_count", "distance_quality_issue",
)
ALERT_COLUMNS = (
    "event_id", "business_unit", "trip_id", "stwid", "event_type", "start_time",
    "acknowledge_time", "state_text", "severity", "source",
)
BILL_COLUMNS = (
    "business_unit", "office", "vendor", "cycle_start", "cycle_end", "trip_id",
    "contract", "slab_name", "total_trip_km", "trip_cost",
)
EMPLOYEE_COLUMNS = (
    "business_unit", "office", "product_type", "trip_date", "shift_type", "trip_id",
    "planned_pickup_epoch", "planned_drop_epoch", "actual_pickup_epoch", "actual_drop_epoch",
    "planned_km", "traveled_km", "stwid", "signin_type", "gender", "employee_role",
    "boarding_status", "not_boarding_reason", "is_no_show", "distance_quality_issue",
)
FEEDBACK_COLUMNS = (
    "business_unit", "trip_id", "trip_type", "trip_at", "stwid", "route_rating",
    "driver_rating", "cab_rating", "safety_rating", "marshal_rating", "creation_time",
)


def text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def nullable_text(value: str | None) -> str | None:
    cleaned = text(value)
    if cleaned is None or cleaned.lower() in {"na", "n/a", "null", "none"}:
        return None
    return cleaned


def integer(value: str | None) -> int | None:
    cleaned = text(value)
    if cleaned is None:
        return None
    try:
        parsed = int(cleaned.replace(",", ""))
        return parsed if -(2**63) <= parsed < 2**63 else None
    except ValueError:
        return None


def number(value: str | None) -> float | None:
    cleaned = text(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned.replace(",", ""))
    except ValueError:
        return None


def money(value: str | None) -> Decimal | None:
    cleaned = text(value)
    if cleaned is None:
        return None
    try:
        return Decimal(cleaned.replace(",", ""))
    except InvalidOperation:
        return None


def epoch(value: str | None) -> int | None:
    cleaned = text(value)
    if cleaned is None:
        return None
    try:
        parsed = Decimal(cleaned.replace(",", ""))
        return int(parsed) if parsed == parsed.to_integral_value() else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


def rating(value: str | None) -> int | None:
    parsed = integer(value)
    return parsed if parsed is not None and 0 <= parsed <= 5 else None


def boolean(value: str | None) -> bool | None:
    cleaned = text(value)
    if cleaned is None:
        return None
    lowered = cleaned.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def parsed_date(value: str | None) -> date | None:
    cleaned = text(value)
    if cleaned is None:
        return None
    for pattern in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            pass
    return None


def parsed_timestamp(value: str | None) -> datetime | None:
    cleaned = text(value)
    if cleaned is None:
        return None
    for pattern in ("%B %d, %Y, %I:%M %p", "%b %d, %Y, %I:%M %p", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(cleaned, pattern)
        except ValueError:
            pass
    return None


def uuid_value(value: str | None) -> UUID | None:
    cleaned = text(value)
    if cleaned is None:
        return None
    try:
        return UUID(cleaned)
    except ValueError:
        return None


def csv_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def trip_row(row: dict[str, str]) -> tuple[Any, ...] | None:
    trip_id = integer(row.get("trip_id"))
    trip_date = parsed_date(row.get("trip_date"))
    if trip_id is None or trip_date is None:
        return None
    nodal = nullable_text(row.get("trip_nodal"))
    planned_km = number(row.get("planned_km"))
    traveled_km = number(row.get("traveled_km"))
    issues: list[str] = []
    if planned_km is not None and planned_km < 0:
        planned_km = None
        issues.append("negative_planned_km")
    if traveled_km is not None and traveled_km < 0:
        traveled_km = None
        issues.append("negative_traveled_km")
    return (
        trip_id, text(row.get("business_unit")), text(row.get("office")),
        text(row.get("product_type")), trip_date, text(row.get("shift_type")),
        text(row.get("trip_direction")), boolean(row.get("actual_escort")), text(row.get("vendor_id")),
        nullable_text(row.get("planned_cab_registration")), text(row.get("actual_cab_registration")),
        integer(row.get("actual_cab_capacity")), planned_km, traveled_km,
        integer(row.get("planned_start_epoch")), integer(row.get("planned_end_epoch")),
        integer(row.get("actual_start_epoch")), integer(row.get("actual_end_epoch")),
        text(row.get("delay_reason")), integer(row.get("delay_minutes")), text(row.get("route_source")),
        text(row.get("actual_cab_fuel_type")), boolean(row.get("is_driver_nc")), boolean(row.get("is_cab_nc")),
        nodal, integer(row.get("plannedemployee_cnt")), integer(row.get("actualemployee_cnt")),
        integer(row.get("noshow_cnt")), ",".join(issues) or None,
    )


def alert_row(row: dict[str, str]) -> tuple[Any, ...] | None:
    event_id = uuid_value(row.get("event_id"))
    if event_id is None:
        return None
    severity = text(row.get("severity"))
    if severity not in {"Sev-1", "Sev-2", "Sev-3"}:
        severity = None
    return (
        event_id, text(row.get("business_unit")), integer(row.get("trip_id")), integer(row.get("stwid")),
        text(row.get("event_type")), parsed_timestamp(row.get("start_time")),
        parsed_timestamp(row.get("acknowledge_time")), text(row.get("state_text")), severity,
        nullable_text(row.get("source")),
    )


def bill_row(row: dict[str, str]) -> tuple[Any, ...]:
    return (
        text(row.get("business_unit")), text(row.get("office")), text(row.get("vendor")),
        parsed_timestamp(row.get("cycle_start")), parsed_timestamp(row.get("cycle_end")),
        integer(row.get("trip_id")), nullable_text(row.get("contract")), nullable_text(row.get("slab_name")),
        number(row.get("total_trip_km")), money(row.get("trip_cost")),
    )


def employee_row(row: dict[str, str]) -> tuple[Any, ...] | None:
    trip_id = integer(row.get("trip_id"))
    if trip_id is None:
        return None
    planned_km = number(row.get("planned_km"))
    traveled_km = number(row.get("traveled_km"))
    issues: list[str] = []
    if planned_km is not None and planned_km < 0:
        planned_km = None
        issues.append("negative_planned_km")
    if traveled_km is not None and traveled_km < 0:
        traveled_km = None
        issues.append("negative_traveled_km")
    return (
        text(row.get("business_unit")), text(row.get("office")), text(row.get("product_type")),
        parsed_date(row.get("trip_date")), text(row.get("shift_type")), trip_id,
        epoch(row.get("planned_pickup_epoch")), epoch(row.get("planned_drop_epoch")),
        epoch(row.get("actual_pickup_epoch")), epoch(row.get("actual_drop_epoch")),
        planned_km, traveled_km, integer(row.get("stwid")), nullable_text(row.get("signintype")),
        nullable_text(row.get("gender")), nullable_text(row.get("emp_role")),
        text(row.get("boarding_status")), nullable_text(row.get("not_boarding_reason")),
        boolean(row.get("is_no_show")), ",".join(issues) or None,
    )


def feedback_row(row: dict[str, str]) -> tuple[Any, ...] | None:
    trip_id = integer(row.get("trip_id"))
    if trip_id is None:
        return None
    return (
        text(row.get("business_unit")), trip_id, text(row.get("trip_type")),
        parsed_timestamp(row.get("trip_date")), integer(row.get("stwid")),
        rating(row.get("route_rating")), rating(row.get("driver_rating")),
        rating(row.get("cab_rating")), rating(row.get("safety_rating")),
        rating(row.get("marshal_rating")), parsed_timestamp(row.get("creation_time")),
    )


def checked_rows(
    paths: Iterable[Path], transform: Callable[[dict[str, str]], tuple[Any, ...] | None],
    seen_index: int | None = None, skip_duplicates: bool = True,
) -> tuple[Iterator[tuple[Any, ...]], dict[str, int]]:
    stats = {"source": 0, "loaded": 0, "skipped": 0, "duplicates": 0}
    seen: set[Any] = set()

    def iterator() -> Iterator[tuple[Any, ...]]:
        for path in paths:
            for raw in csv_rows(path):
                stats["source"] += 1
                clean = transform(raw)
                if clean is None:
                    stats["skipped"] += 1
                    continue
                if seen_index is not None:
                    key = clean[seen_index]
                    if key in seen:
                        stats["duplicates"] += 1
                        if skip_duplicates:
                            stats["skipped"] += 1
                            continue
                    seen.add(key)
                stats["loaded"] += 1
                yield clean

    return iterator(), stats


def copy_rows(connection: psycopg.Connection[Any], table: str, columns: tuple[str, ...], rows: Iterable[tuple[Any, ...]]) -> None:
    statement = f"COPY {table} ({', '.join(columns)}) FROM STDIN"
    with connection.cursor() as cursor, cursor.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)


def scalar(connection: psycopg.Connection[Any], query: str) -> Any:
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchone()[0]


def rows(connection: psycopg.Connection[Any], query: str) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(query)
        return list(cursor.fetchall())


def validation_report(connection: psycopg.Connection[Any]) -> None:
    print("\nVALIDATION REPORT")
    print("TRIPS")
    print("  total rows:", scalar(connection, "SELECT count(*) FROM trips"))
    print("  date range:", rows(connection, "SELECT min(trip_date), max(trip_date) FROM trips")[0])
    print("  distinct trip_id:", scalar(connection, "SELECT count(DISTINCT trip_id) FROM trips"))
    print("  null trip_id:", scalar(connection, "SELECT count(*) FROM trips WHERE trip_id IS NULL"))
    print("  negative distances:", scalar(connection, "SELECT count(*) FROM trips WHERE planned_km < 0 OR traveled_km < 0"))
    print("  cleaned distance anomalies:", scalar(connection, "SELECT count(*) FROM trips WHERE distance_quality_issue IS NOT NULL"))
    print("  by month:", rows(connection, "SELECT to_char(trip_date, 'YYYY-MM'), count(*) FROM trips GROUP BY 1 ORDER BY 1"))
    print("  by business unit:", rows(connection, "SELECT business_unit, count(*) FROM trips GROUP BY 1 ORDER BY 2 DESC"))

    print("ALERTS")
    print("  total rows:", scalar(connection, "SELECT count(*) FROM alerts"))
    print("  distinct event_id:", scalar(connection, "SELECT count(DISTINCT event_id) FROM alerts"))
    print("  null/invalid severity:", scalar(connection, "SELECT count(*) FROM alerts WHERE severity IS NULL"))
    print("  by severity:", rows(connection, "SELECT severity, count(*) FROM alerts GROUP BY 1 ORDER BY 1 NULLS LAST"))
    print("  by event type:", rows(connection, "SELECT event_type, count(*) FROM alerts GROUP BY 1 ORDER BY 2 DESC"))
    print("  unacknowledged:", scalar(connection, "SELECT count(*) FROM alerts WHERE acknowledge_time IS NULL"))
    print("  null source:", scalar(connection, "SELECT count(*) FROM alerts WHERE source IS NULL"))

    print("BILLS")
    print("  total rows:", scalar(connection, "SELECT count(*) FROM bills"))
    print("  distinct trip_id:", scalar(connection, "SELECT count(DISTINCT trip_id) FROM bills"))
    print("  total trip_cost:", scalar(connection, "SELECT sum(trip_cost) FROM bills"))
    print("  zero-km rows:", scalar(connection, "SELECT count(*) FROM bills WHERE total_trip_km = 0"))
    print("  null slab_name:", scalar(connection, "SELECT count(*) FROM bills WHERE slab_name IS NULL"))
    print("  null contract:", scalar(connection, "SELECT count(*) FROM bills WHERE contract IS NULL"))
    print("  null trip_id:", scalar(connection, "SELECT count(*) FROM bills WHERE trip_id IS NULL"))

    print("EMPLOYEE TRIP LEGS")
    print("  total rows:", scalar(connection, "SELECT count(*) FROM employee_trip_legs"))
    print("  distinct trip_id:", scalar(connection, "SELECT count(DISTINCT trip_id) FROM employee_trip_legs"))
    print("  distinct real stwid:", scalar(connection, "SELECT count(DISTINCT stwid) FROM employee_trip_legs WHERE stwid <> 0"))
    print("  placeholder stwid=0:", scalar(connection, "SELECT count(*) FROM employee_trip_legs WHERE stwid = 0"))
    print("  no-shows:", scalar(connection, "SELECT count(*) FROM employee_trip_legs WHERE is_no_show IS TRUE"))
    print("  cleaned distance anomalies:", scalar(connection, "SELECT count(*) FROM employee_trip_legs WHERE distance_quality_issue IS NOT NULL"))

    print("TRIP FEEDBACK")
    print("  total rows:", scalar(connection, "SELECT count(*) FROM trip_feedback"))
    print("  distinct trip_id:", scalar(connection, "SELECT count(DISTINCT trip_id) FROM trip_feedback"))
    print("  distinct real stwid:", scalar(connection, "SELECT count(DISTINCT stwid) FROM trip_feedback WHERE stwid <> 0"))
    print("  zero ratings:", scalar(connection, "SELECT count(*) FROM trip_feedback WHERE route_rating = 0 OR driver_rating = 0 OR cab_rating = 0 OR safety_rating = 0 OR marshal_rating = 0"))

    for child in ("alerts", "bills"):
        total, matched = rows(connection, f"SELECT count(*), count(*) FILTER (WHERE EXISTS (SELECT 1 FROM trips t WHERE t.trip_id = x.trip_id)) FROM {child} x")[0]
        percentage = round((matched / total) * 100, 2) if total else 0
        print(f"JOIN {child}.trip_id -> trips.trip_id: matched={matched}, unmatched={total - matched}, match={percentage}%")

    for child in ("employee_trip_legs", "trip_feedback"):
        total, matched = rows(connection, f"SELECT count(*), count(*) FILTER (WHERE EXISTS (SELECT 1 FROM trips t WHERE t.trip_id = x.trip_id)) FROM {child} x")[0]
        percentage = round((matched / total) * 100, 2) if total else 0
        print(f"JOIN {child}.trip_id -> trips.trip_id: matched={matched}, unmatched={total - matched}, match={percentage}%")

    total, matched = rows(connection, "SELECT count(*), count(*) FILTER (WHERE EXISTS (SELECT 1 FROM employee_trip_legs e WHERE e.trip_id = f.trip_id AND e.stwid = f.stwid)) FROM trip_feedback f")[0]
    percentage = round((matched / total) * 100, 2) if total else 0
    print(f"JOIN trip_feedback.(trip_id, stwid) -> employee_trip_legs: matched={matched}, unmatched={total - matched}, match={percentage}%")


def main() -> int:
    parser = argparse.ArgumentParser(description="Load MoveInSync analytics CSVs into PostgreSQL.")
    parser.add_argument("--data-dir", type=Path, required=True, help="Directory containing the supplied CSV files")
    parser.add_argument("--database-url", default=os.getenv("ANALYTICS_DATABASE_URL"), help="Defaults to ANALYTICS_DATABASE_URL")
    parser.add_argument("--source-check", action="store_true", help="Validate and count source rows without connecting to PostgreSQL")
    parser.add_argument(
        "--datasets", nargs="+", default=["all"],
        choices=("all", "trips", "alerts", "bills", "employees", "feedback"),
        help="Datasets to replace; defaults to all",
    )
    args = parser.parse_args()
    if not args.database_url and not args.source_check:
        parser.error("Set ANALYTICS_DATABASE_URL or pass --database-url")

    selected = {"trips", "alerts", "bills", "employees", "feedback"} if "all" in args.datasets else set(args.datasets)
    specs: dict[str, tuple[list[Path], Callable[[dict[str, str]], tuple[Any, ...] | None], str, tuple[str, ...], int | None, bool]] = {
        "trips": ([args.data_dir / name for name in TRIP_FILES], trip_row, "trips", TRIP_COLUMNS, 0, False),
        "alerts": ([args.data_dir / ALERT_FILE], alert_row, "alerts", ALERT_COLUMNS, 0, True),
        "bills": ([args.data_dir / BILL_FILE], bill_row, "bills", BILL_COLUMNS, None, True),
        "employees": ([args.data_dir / EMPLOYEE_FILE], employee_row, "employee_trip_legs", EMPLOYEE_COLUMNS, None, True),
        "feedback": ([args.data_dir / FEEDBACK_FILE], feedback_row, "trip_feedback", FEEDBACK_COLUMNS, None, True),
    }
    missing = [str(path) for name in selected for path in specs[name][0] if not path.is_file()]
    if missing:
        parser.error("Missing source files: " + ", ".join(missing))

    prepared: dict[str, tuple[Iterator[tuple[Any, ...]], dict[str, int], str, tuple[str, ...]]] = {}
    for name in selected:
        source_paths, transform, table, columns, seen_index, skip_duplicates = specs[name]
        clean_rows, stats = checked_rows(source_paths, transform, seen_index, skip_duplicates)
        prepared[name] = (clean_rows, stats, table, columns)

    if args.source_check:
        for clean_rows, _, _, _ in prepared.values():
            for _ in clean_rows:
                pass
        print("SOURCE CHECK")
        for name in sorted(prepared):
            print(f"  {name}:", prepared[name][1])
        return 0

    with psycopg.connect(args.database_url) as connection:
        with connection.cursor() as cursor:
            tables = ", ".join(prepared[name][2] for name in sorted(prepared))
            cursor.execute(f"TRUNCATE TABLE {tables} RESTART IDENTITY")
        for name in sorted(prepared):
            clean_rows, _, table, columns = prepared[name]
            copy_rows(connection, table, columns, clean_rows)
        connection.commit()
        print("IMPORT SUMMARY")
        for name in sorted(prepared):
            print(f"  {name}:", prepared[name][1])
        validation_report(connection)
    return 0


if __name__ == "__main__":
    sys.exit(main())
