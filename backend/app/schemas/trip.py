from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class TripRow(BaseModel):
    trip_id: str
    vendor_id: str
    route_id: str
    shift_id: str
    employee_id: str
    transport_mode: str
    scheduled_arrival: datetime
    actual_arrival: datetime | None
    status: str
    cost: float | None = None
    distance_km: float | None = None
    rating: float | None = None
    gps_available: bool | None = None

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

    @field_validator("actual_arrival", "cost", "distance_km", "rating", "gps_available", mode="before")
    @classmethod
    def blank_is_none(cls, value: object) -> object:
        return None if value == "" else value