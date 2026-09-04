from collections import Counter
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import Incident, MetricSnapshot, Trip
from app.services.metrics import TripTiming, calculate_ota


INCIDENT_TYPE = "ota_below_sla"


def _severity(ota_value: float, sla_value: float) -> str:
    gap = sla_value - ota_value
    if gap >= 15:
        return "critical"
    if gap >= 5:
        return "high"
    return "warning"


def evaluate_dataset(
    session: Session,
    dataset_upload_id: int,
    settings: Settings,
) -> Incident | None:
    completed = list(
        session.scalars(
            select(Trip).where(
                Trip.dataset_upload_id == dataset_upload_id,
                Trip.status == "completed",
                Trip.actual_arrival.is_not(None),
            )
        )
    )
    timing_by_id = {
        trip.id: TripTiming(trip.scheduled_arrival, trip.actual_arrival)
        for trip in completed
        if trip.actual_arrival is not None
    }
    metrics = calculate_ota(
        list(timing_by_id.values()),
        grace_minutes=settings.ota_grace_minutes,
        minimum_trips=settings.minimum_completed_trips,
    )
    delayed = [
        trip
        for trip in completed
        if trip.actual_arrival is not None
        and (trip.actual_arrival - trip.scheduled_arrival).total_seconds() / 60
        > settings.ota_grace_minutes
    ]
    affected_employees = len({trip.employee_id for trip in delayed})

    snapshot = MetricSnapshot(
        dataset_upload_id=dataset_upload_id,
        ota_value=metrics.on_time_arrival,
        sla_value=settings.ota_sla,
        completed_trips=metrics.completed_trips,
        delayed_trips=metrics.delayed_trips,
        affected_employees=affected_employees,
        average_delay_minutes=metrics.average_delay_minutes,
    )
    session.add(snapshot)

    if metrics.on_time_arrival is None or metrics.on_time_arrival >= settings.ota_sla:
        session.commit()
        return None

    existing = session.scalar(
        select(Incident).where(
            Incident.incident_type == INCIDENT_TYPE,
            Incident.status == "open",
        )
    )
    if existing:
        session.commit()
        return existing

    top_vendor = Counter(trip.vendor_id for trip in delayed).most_common(1)
    top_route = Counter(trip.route_id for trip in delayed).most_common(1)
    top_shift = Counter(trip.shift_id for trip in delayed).most_common(1)
    vendor = top_vendor[0][0] if top_vendor else None
    missing_gps = sum(trip.gps_available is not True for trip in completed)
    warning = (
        f"GPS unavailable for {missing_gps} completed trip(s)."
        if missing_gps
        else None
    )
    reason = (
        f"{vendor} contributed the most delayed trips in this dataset."
        if vendor
        else "No single contributing vendor could be identified."
    )
    incident = Incident(
        incident_type=INCIDENT_TYPE,
        title="On-time arrival below SLA",
        severity=_severity(metrics.on_time_arrival, settings.ota_sla),
        current_value=metrics.on_time_arrival,
        sla_value=settings.ota_sla,
        previous_value=None,
        affected_employees=affected_employees,
        contributing_vendor=vendor,
        contributing_route=top_route[0][0] if top_route else None,
        contributing_shift=top_shift[0][0] if top_shift else None,
        reason=reason,
        recommended_action=(
            f"Review {vendor}'s upcoming trips and confirm a recovery plan before the next shift."
            if vendor
            else "Review delayed trips and assign an owner for the next shift."
        ),
        data_quality_warning=warning,
        created_at=datetime.utcnow(),
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident