from sqlalchemy import Engine, inspect, text

from app.database.connection import Base
from app.database import models as _models


INCIDENT_COLUMNS = {
    "updated_at": "DATETIME",
    "acknowledged_value": "FLOAT",
    "last_notified_at": "DATETIME",
    "last_notified_value": "FLOAT",
    "notification_count": "INTEGER DEFAULT 1",
    "attention_required": "BOOLEAN DEFAULT 1",
}

TRIP_COLUMNS = {
    "employee_count": "INTEGER DEFAULT 1",
    "office_id": "VARCHAR(150)",
    "no_show_count": "INTEGER DEFAULT 0",
    "delay_reason": "VARCHAR(255)",
    "reported_delay_minutes": "FLOAT",
    "driver_non_compliance": "BOOLEAN",
    "cab_non_compliance": "BOOLEAN",
}


def migrate_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    normalized_trip_columns = {
        column["name"] for column in inspector.get_columns("shlok_trips")
    }
    if "reported_delay_minutes" not in normalized_trip_columns:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE shlok_trips ADD COLUMN reported_delay_minutes FLOAT"
            ))
    with engine.begin() as connection:
        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_shlok_trips_scheduled_arrival ON shlok_trips (scheduled_arrival)",
            "CREATE INDEX IF NOT EXISTS ix_shlok_trips_delay_reason ON shlok_trips (delay_reason)",
            "CREATE INDEX IF NOT EXISTS ix_shlok_trips_reported_delay_minutes ON shlok_trips (reported_delay_minutes)",
            "CREATE INDEX IF NOT EXISTS ix_shlok_trip_feedback_trip_type ON shlok_trip_feedback (trip_type)",
            "CREATE INDEX IF NOT EXISTS ix_shlok_safety_alerts_source ON shlok_safety_alerts (source)",
        ):
            connection.execute(text(statement))
    if engine.dialect.name != "sqlite":
        return

    tables = set(inspector.get_table_names())
    existing = {column["name"] for column in inspector.get_columns("incidents")}
    existing_trip_columns = (
        {column["name"] for column in inspector.get_columns("trips")}
        if "trips" in tables
        else set()
    )
    added_lifecycle_columns = False
    with engine.begin() as connection:
        if "id" in existing_trip_columns:
            for name, definition in TRIP_COLUMNS.items():
                if name not in existing_trip_columns:
                    connection.execute(text(f"ALTER TABLE trips ADD COLUMN {name} {definition}"))
            connection.execute(text(
                "UPDATE trips SET "
                "employee_count = COALESCE(employee_count, 1), "
                "no_show_count = COALESCE(no_show_count, 0)"
            ))
            connection.execute(text(
                "INSERT OR IGNORE INTO shlok_trips ("
                "id, dataset_upload_id, trip_id, vendor_id, route_id, shift_id, employee_id, "
                "employee_count, office_id, no_show_count, transport_mode, scheduled_arrival, "
                "actual_arrival, status, cost, distance_km, rating, gps_available, delay_reason, "
                "reported_delay_minutes, driver_non_compliance, cab_non_compliance"
                ") SELECT id, dataset_upload_id, trip_id, vendor_id, route_id, shift_id, employee_id, "
                "employee_count, office_id, no_show_count, transport_mode, scheduled_arrival, "
                "actual_arrival, status, cost, distance_km, rating, gps_available, delay_reason, "
                "reported_delay_minutes, driver_non_compliance, cab_non_compliance FROM trips"
            ))
        if "safety_alerts" in tables:
            connection.execute(text(
                "INSERT OR IGNORE INTO shlok_safety_alerts ("
                "id, trip_id, employee_id, event_id, event_type, started_at, acknowledged_at, state, severity, source"
                ") SELECT id, trip_id, employee_id, event_id, event_type, started_at, acknowledged_at, state, severity, source "
                "FROM safety_alerts"
            ))
        if "trip_feedback" in tables and "employee_id" in {
            column["name"] for column in inspector.get_columns("trip_feedback")
        }:
            connection.execute(text(
                "INSERT OR IGNORE INTO shlok_trip_feedback ("
                "id, trip_id, employee_id, trip_type, trip_at, route_rating, driver_rating, "
                "cab_rating, safety_rating, marshal_rating, created_at"
                ") SELECT id, trip_id, employee_id, trip_type, trip_at, route_rating, driver_rating, "
                "cab_rating, safety_rating, marshal_rating, created_at FROM trip_feedback"
            ))
        for name, definition in INCIDENT_COLUMNS.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE incidents ADD COLUMN {name} {definition}"))
                added_lifecycle_columns = True
        if added_lifecycle_columns:
            connection.execute(text("DELETE FROM incidents WHERE incident_type LIKE '%:dataset:%'"))
        connection.execute(
            text(
                "UPDATE incidents SET "
                "updated_at = COALESCE(updated_at, created_at), "
                "acknowledged_value = CASE "
                "WHEN status = 'acknowledged' THEN COALESCE(acknowledged_value, current_value) "
                "ELSE acknowledged_value END, "
                "attention_required = CASE WHEN status IN ('open', 'reopened') THEN 1 ELSE 0 END, "
                "notification_count = COALESCE(notification_count, 1), "
                "last_notified_value = COALESCE(last_notified_value, current_value), "
                "last_notified_at = COALESCE(last_notified_at, created_at)"
            )
        )