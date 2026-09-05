from collections import Counter
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import Incident, IncidentEvent, MetricSnapshot, Trip
from app.services.metrics import TripTiming, calculate_ota


SEVERITY_RANK = {"warning": 1, "high": 2, "critical": 3}


def _severity(value: float, sla_value: float) -> str:
    gap = sla_value - value
    if gap >= 15:
        return "critical"
    if gap >= 5:
        return "high"
    return "warning"


def _active_incident(session: Session, incident_type: str) -> Incident | None:
    return session.scalar(
        select(Incident)
        .where(Incident.incident_type == incident_type, Incident.status != "resolved")
        .order_by(desc(Incident.id))
        .limit(1)
    )


def _record_event(
    session: Session,
    incident: Incident,
    event_type: str,
    value: float,
    message: str,
) -> None:
    session.add(
        IncidentEvent(
            incident_id=incident.id,
            event_type=event_type,
            metric_value=value,
            message=message,
        )
    )


def _apply_signal(
    session: Session,
    settings: Settings,
    *,
    incident_type: str,
    title: str,
    current_value: float,
    sla_value: float,
    affected_employees: int,
    reason: str,
    recommended_action: str,
    contributing_vendor: str | None = None,
    contributing_route: str | None = None,
    contributing_shift: str | None = None,
    data_quality_warning: str | None = None,
) -> tuple[Incident | None, bool]:
    now = datetime.utcnow()
    incident = _active_incident(session, incident_type)

    if current_value >= sla_value:
        if incident is not None:
            incident.previous_value = incident.current_value
            incident.current_value = current_value
            incident.status = "resolved"
            incident.attention_required = False
            incident.updated_at = now
            _record_event(
                session,
                incident,
                "resolved",
                current_value,
                f"Recovered to {current_value}% against the {sla_value}% target.",
            )
        return incident, False

    severity = _severity(current_value, sla_value)
    if incident is None:
        incident = Incident(
            incident_type=incident_type,
            title=title,
            severity=severity,
            status="open",
            current_value=current_value,
            sla_value=sla_value,
            previous_value=None,
            affected_employees=affected_employees,
            contributing_vendor=contributing_vendor,
            contributing_route=contributing_route,
            contributing_shift=contributing_shift,
            reason=reason,
            recommended_action=recommended_action,
            data_quality_warning=data_quality_warning,
            created_at=now,
            updated_at=now,
            last_notified_at=now,
            last_notified_value=current_value,
            notification_count=1,
            attention_required=True,
        )
        session.add(incident)
        session.flush()
        _record_event(
            session,
            incident,
            "opened",
            current_value,
            f"Opened at {current_value}% against the {sla_value}% target.",
        )
        return incident, True

    previous_value = incident.current_value
    previous_severity = incident.severity
    incident.previous_value = previous_value
    incident.current_value = current_value
    incident.severity = severity
    incident.affected_employees = affected_employees
    incident.contributing_vendor = contributing_vendor
    incident.contributing_route = contributing_route
    incident.contributing_shift = contributing_shift
    incident.reason = reason
    incident.recommended_action = recommended_action
    incident.data_quality_warning = data_quality_warning
    incident.updated_at = now

    acknowledged_drop = (
        incident.acknowledged_value is not None
        and incident.acknowledged_value - current_value >= settings.incident_reopen_drop_points
    )
    severity_increased = SEVERITY_RANK[severity] > SEVERITY_RANK[previous_severity]
    should_notify = severity_increased or (
        incident.status == "acknowledged" and acknowledged_drop
    )
    if should_notify:
        was_acknowledged = incident.status == "acknowledged"
        incident.status = "reopened" if was_acknowledged else incident.status
        incident.attention_required = True
        incident.last_notified_at = now
        incident.last_notified_value = current_value
        incident.notification_count += 1
        event_type = "reopened" if was_acknowledged else "escalated"
        _record_event(
            session,
            incident,
            event_type,
            current_value,
            f"Metric worsened from {previous_value}% to {current_value}%; manager attention is required again.",
        )
    return incident, should_notify


def evaluate_operations(
    session: Session,
    dataset_upload_id: int,
    settings: Settings,
) -> Incident | None:
    completed = list(
        session.scalars(
            select(Trip).where(
                Trip.status == "completed",
                Trip.actual_arrival.is_not(None),
            )
        )
    )
    timings = {
        trip.id: TripTiming(
            trip.scheduled_arrival,
            trip.actual_arrival,
            trip.reported_delay_minutes,
        )
        for trip in completed
        if trip.actual_arrival is not None
    }
    metrics = calculate_ota(
        list(timings.values()),
        grace_minutes=settings.ota_grace_minutes,
        minimum_trips=settings.minimum_completed_trips,
    )
    delayed = [
        trip
        for trip in completed
        if trip.actual_arrival is not None
        and (
            trip.reported_delay_minutes > 0
            if trip.reported_delay_minutes is not None
            else (trip.actual_arrival - trip.scheduled_arrival).total_seconds() / 60
            > settings.ota_grace_minutes
        )
    ]
    affected_employees = sum(trip.employee_count for trip in delayed)
    session.add(
        MetricSnapshot(
            dataset_upload_id=dataset_upload_id,
            ota_value=metrics.on_time_arrival,
            sla_value=settings.ota_sla,
            completed_trips=metrics.completed_trips,
            delayed_trips=metrics.delayed_trips,
            affected_employees=affected_employees,
            average_delay_minutes=metrics.average_delay_minutes,
        )
    )

    notified_incident: Incident | None = None
    top_vendor = Counter(trip.vendor_id for trip in delayed).most_common(1)
    top_route = Counter(trip.route_id for trip in delayed).most_common(1)
    top_shift = Counter(trip.shift_id for trip in delayed).most_common(1)
    vendor = top_vendor[0][0] if top_vendor else None
    missing_gps = sum(trip.gps_available is False for trip in completed)
    warning = f"GPS unavailable for {missing_gps} completed trip(s)." if missing_gps else None

    if metrics.on_time_arrival is not None:
        incident, notified = _apply_signal(
            session,
            settings,
            incident_type="ota_below_sla",
            title="On-time arrival below SLA",
            current_value=metrics.on_time_arrival,
            sla_value=settings.ota_sla,
            affected_employees=affected_employees,
            contributing_vendor=vendor,
            contributing_route=top_route[0][0] if top_route else None,
            contributing_shift=top_shift[0][0] if top_shift else None,
            reason=f"{vendor} currently contributes the most delayed trips." if vendor else "No single contributing vendor could be identified.",
            recommended_action=f"Review {vendor}'s upcoming trips and confirm a recovery plan." if vendor else "Review delayed trips and assign an owner.",
            data_quality_warning=warning,
        )
        if notified:
            notified_incident = incident

    for vendor_id in sorted({trip.vendor_id for trip in completed}):
        vendor_trips = [trip for trip in completed if trip.vendor_id == vendor_id]
        vendor_metrics = calculate_ota(
            [timings[trip.id] for trip in vendor_trips],
            grace_minutes=settings.ota_grace_minutes,
            minimum_trips=settings.vendor_minimum_completed_trips,
        )
        if vendor_metrics.on_time_arrival is None:
            continue
        vendor_delayed = [trip for trip in delayed if trip.vendor_id == vendor_id]
        incident, notified = _apply_signal(
            session,
            settings,
            incident_type=f"vendor_ota_below_sla:{vendor_id}",
            title=f"{vendor_id} on-time arrival below SLA",
            current_value=vendor_metrics.on_time_arrival,
            sla_value=settings.ota_sla,
            affected_employees=sum(trip.employee_count for trip in vendor_delayed),
            contributing_vendor=vendor_id,
            contributing_route=Counter(trip.route_id for trip in vendor_delayed).most_common(1)[0][0] if vendor_delayed else None,
            contributing_shift=Counter(trip.shift_id for trip in vendor_delayed).most_common(1)[0][0] if vendor_delayed else None,
            reason=f"{vendor_id} has {vendor_metrics.delayed_trips} delayed trips across {len(vendor_trips)} completed trips.",
            recommended_action=f"Ask {vendor_id} for a route-level recovery plan before assigning more trips.",
        )
        if notified and notified_incident is None:
            notified_incident = incident

    gps_observations = [trip for trip in completed if trip.gps_available is not None]
    if gps_observations:
        gps_available = sum(trip.gps_available is True for trip in gps_observations)
        gps_value = round((gps_available / len(gps_observations)) * 100, 2)
        gps_affected_employees = sum(
            trip.employee_count
            for trip in gps_observations
            if trip.gps_available is False
        )
        incident, notified = _apply_signal(
            session,
            settings,
            incident_type="gps_availability_below_sla",
            title="GPS availability below target",
            current_value=gps_value,
            sla_value=settings.gps_availability_sla,
            affected_employees=gps_affected_employees,
            reason=f"GPS is available for {gps_available} of {len(gps_observations)} observed trips.",
            recommended_action="Verify device connectivity and follow up on trips without GPS evidence.",
            data_quality_warning=warning,
        )
        if notified and notified_incident is None:
            notified_incident = incident

    session.commit()
    return notified_incident


evaluate_dataset = evaluate_operations
