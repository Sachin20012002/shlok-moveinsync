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
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_upload_id: Mapped[int] = mapped_column(ForeignKey("dataset_uploads.id"))
    trip_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    vendor_id: Mapped[str] = mapped_column(String(100), index=True)
    route_id: Mapped[str] = mapped_column(String(100), index=True)
    shift_id: Mapped[str] = mapped_column(String(100), index=True)
    employee_id: Mapped[str] = mapped_column(String(100), index=True)
    transport_mode: Mapped[str] = mapped_column(String(50))
    scheduled_arrival: Mapped[datetime] = mapped_column(DateTime)
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), index=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


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
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)