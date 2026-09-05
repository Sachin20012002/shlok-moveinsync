from collections import defaultdict

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import DatasetUpload, Incident, IncidentEvent, Trip
from app.schemas.api import OperationsResponse


EXCEPTION_SAMPLE_SIZE = 50


def _delay_minutes(trip: Trip) -> float | None:
    if trip.actual_arrival is None:
        return None
    return round(
        max(0.0, (trip.actual_arrival - trip.scheduled_arrival).total_seconds() / 60),
        2,
    )


def build_operations_response(session: Session, settings: Settings) -> OperationsResponse:
    trips = list(session.scalars(select(Trip).order_by(desc(Trip.scheduled_arrival))))
    incidents = list(session.scalars(select(Incident)))
    attention_incidents = [incident for incident in incidents if incident.attention_required]
    active_incidents = {
        incident.incident_type: incident.id
        for incident in incidents
        if incident.status != "resolved"
    }
    completed = [
        trip for trip in trips
        if trip.status == "completed" and trip.actual_arrival is not None
    ]

    exception_samples: dict[int | None, list[dict[str, object]]] = defaultdict(list)
    incident_trip_counts: dict[int, int] = defaultdict(int)
    total_trip_exceptions = 0

    def add_sample(bucket: int | None, exception: dict[str, object]) -> None:
        sample = exception_samples[bucket]
        sample.append(exception)
        sample.sort(key=lambda item: float(item["delayMinutes"] or 0), reverse=True)
        del sample[EXCEPTION_SAMPLE_SIZE:]

    for trip in trips:
        delay = _delay_minutes(trip)
        issues = []
        related_incident_ids = []
        if trip.actual_arrival is None:
            issues.append("Arrival missing")
        elif delay is not None and delay > settings.ota_grace_minutes:
            issues.append(f"{delay:g} min late")
            for incident_type in (
                "ota_below_sla",
                f"vendor_ota_below_sla:{trip.vendor_id}",
            ):
                if incident_type in active_incidents:
                    related_incident_ids.append(active_incidents[incident_type])
        if trip.gps_available is False:
            issues.append("GPS unavailable")
            gps_incident_id = active_incidents.get("gps_availability_below_sla")
            if gps_incident_id is not None:
                related_incident_ids.append(gps_incident_id)
        if issues:
            exception = {
                "tripId": trip.trip_id,
                "issue": " · ".join(issues),
                "delayMinutes": delay,
                "relatedIncidentIds": related_incident_ids,
                "vendorId": trip.vendor_id,
                "routeId": trip.route_id,
                "employeeId": trip.employee_id,
                "employeeCount": trip.employee_count,
                "recommendedAction": (
                    "Contact vendor and verify arrival"
                    if trip.actual_arrival is None
                    else "Verify device connectivity"
                    if trip.gps_available is False and (delay or 0) <= settings.ota_grace_minutes
                    else "Review route execution with vendor"
                ),
            }
            total_trip_exceptions += 1
            add_sample(None, exception)
            for incident_id in related_incident_ids:
                incident_trip_counts[incident_id] += 1
                add_sample(incident_id, exception)

    exceptions_by_trip_id = {
        str(exception["tripId"]): exception
        for samples in exception_samples.values()
        for exception in samples
    }
    exceptions = sorted(
        exceptions_by_trip_id.values(),
        key=lambda item: float(item["delayMinutes"] or 0),
        reverse=True,
    )

    shifts: dict[str, list[Trip]] = defaultdict(list)
    vendors: dict[str, list[Trip]] = defaultdict(list)
    for trip in trips:
        shifts[trip.shift_id].append(trip)
        vendors[trip.vendor_id].append(trip)

    shift_readiness = []
    for shift_id, shift_trips in sorted(shifts.items()):
        shift_completed = [trip for trip in shift_trips if trip in completed]
        shift_delayed = [
            trip for trip in shift_completed
            if (_delay_minutes(trip) or 0) > settings.ota_grace_minutes
        ]
        missing_arrivals = sum(trip.actual_arrival is None for trip in shift_trips)
        delayed_ratio = len(shift_delayed) / len(shift_completed) if shift_completed else 0
        readiness = "critical" if missing_arrivals or delayed_ratio >= 0.3 else "at_risk" if shift_delayed else "ready"
        shift_readiness.append(
            {
                "shiftId": shift_id,
                "completedTrips": len(shift_completed),
                "delayedTrips": len(shift_delayed),
                "missingArrivals": missing_arrivals,
                "affectedEmployees": sum(trip.employee_count for trip in shift_delayed),
                "status": readiness,
            }
        )

    vendor_watchlist = []
    for vendor_id, vendor_trips in sorted(vendors.items()):
        vendor_completed = [trip for trip in vendor_trips if trip in completed]
        if not vendor_completed:
            continue
        delayed_count = sum(
            (_delay_minutes(trip) or 0) > settings.ota_grace_minutes
            for trip in vendor_completed
        )
        ota = round(((len(vendor_completed) - delayed_count) / len(vendor_completed)) * 100, 2)
        missing_gps = sum(trip.gps_available is False for trip in vendor_completed)
        vendor_incidents = sum(
            incident.contributing_vendor == vendor_id and incident.attention_required
            for incident in incidents
        )
        if ota < settings.ota_sla or missing_gps:
            vendor_watchlist.append(
                {
                    "vendorId": vendor_id,
                    "ota": ota,
                    "delayedTrips": delayed_count,
                    "missingGps": missing_gps,
                    "attentionIncidents": vendor_incidents,
                }
            )
    vendor_watchlist.sort(key=lambda item: (item["ota"], -item["delayedTrips"]))

    event_rows = session.execute(
        select(IncidentEvent, Incident.title)
        .join(Incident, Incident.id == IncidentEvent.incident_id)
        .order_by(desc(IncidentEvent.created_at))
        .limit(8)
    ).all()
    latest_upload = session.scalar(
        select(DatasetUpload).order_by(desc(DatasetUpload.uploaded_at)).limit(1)
    )

    return OperationsResponse(
        active_trips=sum(
            trip.status.lower() in {"scheduled", "assigned", "in_progress", "started"}
            for trip in trips
        ),
        maximum_delay_minutes=max((_delay_minutes(trip) or 0 for trip in completed), default=None),
        total_trip_exceptions=total_trip_exceptions,
        trip_exceptions=exceptions,
        incident_trip_counts=[
            {"incidentId": incident_id, "count": count}
            for incident_id, count in incident_trip_counts.items()
        ],
        shift_readiness=shift_readiness,
        vendor_watchlist=vendor_watchlist[:6],
        timeline=[
            {
                "incidentId": event.incident_id,
                "title": title,
                "eventType": event.event_type,
                "message": event.message,
                "createdAt": event.created_at,
            }
            for event, title in event_rows
        ],
        data_quality={
            "sourceFile": latest_upload.filename if latest_upload else None,
            "importedRows": latest_upload.valid_rows if latest_upload else 0,
            "missingGps": sum(trip.gps_available is False for trip in trips),
            "missingArrivals": sum(trip.actual_arrival is None for trip in trips),
            "invalidRows": sum(upload.invalid_rows for upload in session.scalars(select(DatasetUpload))),
            "skippedRows": sum(upload.skipped_rows for upload in session.scalars(select(DatasetUpload))),
            "lastDataUpdate": latest_upload.uploaded_at if latest_upload else None,
        },
        recommended_actions=[
            {
                "incidentId": incident.id,
                "severity": incident.severity,
                "title": incident.title,
                "action": incident.recommended_action,
            }
            for incident in sorted(
                attention_incidents,
                key=lambda item: ({"critical": 3, "high": 2, "warning": 1}[item.severity], item.updated_at),
                reverse=True,
            )[:5]
        ],
    )