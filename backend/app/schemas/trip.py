from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class TripRow(BaseModel):
    trip_id: str
    vendor_id: str
    route_id: str
    shift_id: str
    employee_id: str
    employee_count: int = 1
    office_id: str | None = None
    no_show_count: int = 0
    transport_mode: str
    scheduled_arrival: datetime
    actual_arrival: datetime | None
    status: str
    cost: float | None = None
    distance_km: float | None = None
    rating: float | None = None
    gps_available: bool | None = None
    delay_reason: str | None = None
    reported_delay_minutes: float | None = None
    driver_non_compliance: bool | None = None
    cab_non_compliance: bool | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator(
        "trip_id",
        "vendor_id",
        "route_id",
        "shift_id",
        "employee_id",
        "transport_mode",
        "status",
    )
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value:
            raise ValueError("value is required")
        return value

    @field_validator(
        "actual_arrival",
        "cost",
        "distance_km",
        "rating",
        "gps_available",
        "office_id",
        "delay_reason",
        "reported_delay_minutes",
        "driver_non_compliance",
        "cab_non_compliance",
        mode="before",
    )
    @classmethod
    def blank_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("employee_count", "no_show_count")
    @classmethod
    def require_positive_employee_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("count cannot be negative")
        return value