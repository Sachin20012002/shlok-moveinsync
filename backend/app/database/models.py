from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class DatasetUpload(Base):
    __tablename__ = "dataset_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    valid_rows: Mapped[int] = mapped_column(Integer)
    invalid_rows: Mapped[int] = mapped_column(Integer)
    skipped_rows: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Trip(Base):
    __tablename__ = "shlok_trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_upload_id: Mapped[int] = mapped_column(ForeignKey("dataset_uploads.id"))
    trip_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    vendor_id: Mapped[str] = mapped_column(String(100), index=True)
    route_id: Mapped[str] = mapped_column(String(100), index=True)
    shift_id: Mapped[str] = mapped_column(String(100), index=True)
    employee_id: Mapped[str] = mapped_column(String(100), index=True)
    employee_count: Mapped[int] = mapped_column(Integer, default=1)
    office_id: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    no_show_count: Mapped[int] = mapped_column(Integer, default=0)
    transport_mode: Mapped[str] = mapped_column(String(50))
    scheduled_arrival: Mapped[datetime] = mapped_column(DateTime, index=True)
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), index=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    delay_reason: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    reported_delay_minutes: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    driver_non_compliance: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cab_non_compliance: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class SafetyAlert(Base):
    __tablename__ = "shlok_safety_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(100), index=True)
    employee_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    state: Mapped[str] = mapped_column(String(30), index=True)
    severity: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)


class TripFeedback(Base):
    __tablename__ = "shlok_trip_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(100), index=True)
    employee_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    trip_type: Mapped[str] = mapped_column(String(20), index=True)
    trip_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    route_rating: Mapped[int] = mapped_column(Integer)
    driver_rating: Mapped[int] = mapped_column(Integer)
    cab_rating: Mapped[int] = mapped_column(Integer)
    safety_rating: Mapped[int] = mapped_column(Integer)
    marshal_rating: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_upload_id: Mapped[int] = mapped_column(ForeignKey("dataset_uploads.id"))
    ota_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sla_value: Mapped[float] = mapped_column(Float)
    completed_trips: Mapped[int] = mapped_column(Integer)
    delayed_trips: Mapped[int] = mapped_column(Integer)
    affected_employees: Mapped[int] = mapped_column(Integer)
    average_delay_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_type: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    current_value: Mapped[float] = mapped_column(Float)
    sla_value: Mapped[float] = mapped_column(Float)
    previous_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    affected_employees: Mapped[int] = mapped_column(Integer)
    contributing_vendor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contributing_route: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contributing_shift: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    data_quality_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_notified_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    notification_count: Mapped[int] = mapped_column(Integer, default=1)
    attention_required: Mapped[bool] = mapped_column(Boolean, default=True)


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    metric_value: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)