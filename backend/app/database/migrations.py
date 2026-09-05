from sqlalchemy import Engine, inspect, text

from app.database.connection import Base


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
    "driver_non_compliance": "BOOLEAN",
    "cab_non_compliance": "BOOLEAN",
}


def migrate_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns("incidents")}
    existing_trip_columns = {column["name"] for column in inspector.get_columns("trips")}
    added_lifecycle_columns = False
    with engine.begin() as connection:
        for name, definition in TRIP_COLUMNS.items():
            if name not in existing_trip_columns:
                connection.execute(text(f"ALTER TABLE trips ADD COLUMN {name} {definition}"))
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
        connection.execute(text(
            "UPDATE trips SET "
            "employee_count = COALESCE(employee_count, 1), "
            "no_show_count = COALESCE(no_show_count, 0)"
        ))