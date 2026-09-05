from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import psycopg

from import_data import (
    ALERT_COLUMNS,
    ALERT_FILE,
    BILL_COLUMNS,
    BILL_FILE,
    EMPLOYEE_COLUMNS,
    EMPLOYEE_FILE,
    FEEDBACK_COLUMNS,
    FEEDBACK_FILE,
    TRIP_COLUMNS,
    TRIP_FILES,
    alert_row,
    bill_row,
    copy_rows,
    csv_rows,
    employee_row,
    feedback_row,
    trip_row,
    validation_report,
)


RESET_TABLES = (
    "incident_events",
    "incidents",
    "metric_snapshots",
    "dataset_uploads",
    "employee_trip_legs",
    "trip_feedback",
    "alerts",
    "bills",
    "sla_config",
    "trips",
)


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected YYYY-MM-DD") from error


def migration_sql(path: Path) -> str:
    statements = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().upper() in {"BEGIN;", "COMMIT;"}:
            continue
        statements.append(line)
    return "\n".join(statements)


def filtered_rows(
    paths: list[Path],
    transform: Callable[[dict[str, str]], tuple[Any, ...] | None],
    include: Callable[[tuple[Any, ...]], bool],
    *,
    unique_index: int | None = None,
) -> tuple[Iterator[tuple[Any, ...]], dict[str, int]]:
    stats = {"source": 0, "loaded": 0, "filtered": 0, "invalid": 0, "duplicates": 0}
    seen: set[Any] = set()

    def iterator() -> Iterator[tuple[Any, ...]]:
        for path in paths:
            for raw in csv_rows(path):
                stats["source"] += 1
                clean = transform(raw)
                if clean is None:
                    stats["invalid"] += 1
                    continue
                if not include(clean):
                    stats["filtered"] += 1
                    continue
                if unique_index is not None:
                    key = clean[unique_index]
                    if key in seen:
                        stats["duplicates"] += 1
                        continue
                    seen.add(key)
                stats["loaded"] += 1
                yield clean

    return iterator(), stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace Neon tables with a coherent, size-limited MoveInSync demo subset."
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--start-date", type=parse_iso_date, default=date(2026, 7, 18))
    parser.add_argument("--end-date", type=parse_iso_date, default=date(2026, 7, 31))
    parser.add_argument(
        "--database-url",
        default=os.getenv("ANALYTICS_DATABASE_URL"),
        help="Defaults to ANALYTICS_DATABASE_URL",
    )
    parser.add_argument(
        "--reset-existing",
        action="store_true",
        help="Required acknowledgement that managed and legacy backend tables will be replaced",
    )
    args = parser.parse_args()

    if not args.database_url:
        parser.error("Set ANALYTICS_DATABASE_URL or pass --database-url")
    if not args.reset_existing:
        parser.error("Pass --reset-existing to acknowledge destructive replacement")
    if args.start_date > args.end_date:
        parser.error("--start-date must be on or before --end-date")

    paths = {
        "trips": [args.data_dir / name for name in TRIP_FILES],
        "alerts": [args.data_dir / ALERT_FILE],
        "bills": [args.data_dir / BILL_FILE],
        "employees": [args.data_dir / EMPLOYEE_FILE],
        "feedback": [args.data_dir / FEEDBACK_FILE],
    }
    missing = [str(path) for group in paths.values() for path in group if not path.is_file()]
    if missing:
        parser.error("Missing source files: " + ", ".join(missing))

    selected_trip_keys: set[tuple[int, date]] = set()
    selected_trip_ids: set[int] = set()
    for path in paths["trips"]:
        for raw in csv_rows(path):
            clean = trip_row(raw)
            if clean is None:
                continue
            trip_id, trip_date = clean[0], clean[4]
            if args.start_date <= trip_date <= args.end_date:
                selected_trip_keys.add((trip_id, trip_date))
                selected_trip_ids.add(trip_id)

    if not selected_trip_keys:
        parser.error("The selected date window contains no valid trips")

    trip_rows, trip_stats = filtered_rows(
        paths["trips"],
        trip_row,
        lambda row: (row[0], row[4]) in selected_trip_keys,
    )
    employee_rows, employee_stats = filtered_rows(
        paths["employees"],
        employee_row,
        lambda row: row[3] is not None and (row[5], row[3]) in selected_trip_keys,
    )
    feedback_rows, feedback_stats = filtered_rows(
        paths["feedback"],
        feedback_row,
        lambda row: row[3] is not None and (row[1], row[3].date()) in selected_trip_keys,
    )
    alert_rows, alert_stats = filtered_rows(
        paths["alerts"],
        alert_row,
        lambda row: (
            row[2] in selected_trip_ids
            and row[5] is not None
            and args.start_date <= row[5].date() <= args.end_date
        ),
        unique_index=0,
    )
    bill_rows, bill_stats = filtered_rows(
        paths["bills"],
        bill_row,
        lambda row: row[5] in selected_trip_ids,
    )

    project_root = Path(__file__).resolve().parent
    migrations = [
        project_root / "migrations" / "001_analytics_schema.sql",
        project_root / "migrations" / "002_employee_feedback.sql",
        project_root / "migrations" / "003_trip_quality.sql",
    ]

    with psycopg.connect(args.database_url) as connection:
        with connection.cursor() as cursor:
            quoted = ", ".join(f'"{table}"' for table in RESET_TABLES)
            cursor.execute(f"DROP TABLE IF EXISTS {quoted} CASCADE")
            for migration in migrations:
                cursor.execute(migration_sql(migration))

        loads = (
            ("trips", TRIP_COLUMNS, trip_rows, trip_stats),
            ("employee_trip_legs", EMPLOYEE_COLUMNS, employee_rows, employee_stats),
            ("trip_feedback", FEEDBACK_COLUMNS, feedback_rows, feedback_stats),
            ("alerts", ALERT_COLUMNS, alert_rows, alert_stats),
            ("bills", BILL_COLUMNS, bill_rows, bill_stats),
        )
        for table, columns, records, stats in loads:
            print(f"Loading {table}...", flush=True)
            copy_rows(connection, table, columns, records)
            print(f"  {stats}", flush=True)

        validation_report(connection)
        size = connection.execute(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        ).fetchone()[0]
        print("DATABASE SIZE BEFORE COMMIT:", size)
        connection.commit()
        print("IMPORT COMMITTED")

    return 0


if __name__ == "__main__":
    sys.exit(main())
