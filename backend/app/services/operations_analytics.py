from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import Incident, Trip


def _is_delayed(trip: Trip, settings: Settings) -> bool:
    if trip.reported_delay_minutes is not None:
        return trip.reported_delay_minutes > 0
    if trip.actual_arrival is None:
        return False
    return (trip.actual_arrival - trip.scheduled_arrival).total_seconds() / 60 > settings.ota_grace_minutes


def _delay_minutes(trip: Trip) -> float:
    if trip.reported_delay_minutes is not None:
        return max(0.0, trip.reported_delay_minutes)
    if trip.actual_arrival is None:
        return 0.0
    return max(0.0, (trip.actual_arrival - trip.scheduled_arrival).total_seconds() / 60)


def _performance(trips: list[Trip], settings: Settings) -> dict[str, Any]:
    completed = [trip for trip in trips if trip.status.lower() == "completed" and trip.actual_arrival is not None]
    delayed = [trip for trip in completed if _is_delayed(trip, settings)]
    return {
        "completedTrips": len(completed),
        "delayedTrips": len(delayed),
        "ota": round(((len(completed) - len(delayed)) / len(completed)) * 100, 2) if completed else None,
        "affectedEmployees": sum(trip.employee_count for trip in delayed),
        "averageDelayMinutes": round(sum(_delay_minutes(trip) for trip in delayed) / len(delayed), 2) if delayed else 0.0,
    }


def get_operations_analytics(
    session: Session,
    settings: Settings,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    minimum, maximum = session.execute(
        select(func.min(Trip.scheduled_arrival), func.max(Trip.scheduled_arrival))
    ).one()
    if minimum is None or maximum is None:
        return {
            "availableRange": {"startDate": None, "endDate": None},
            "selectedRange": {"startDate": None, "endDate": None},
            "summary": _performance([], settings),
            "vendorPerformance": [],
            "shiftPerformance": [],
            "weeklyTrend": [],
        }

    resolved_start = start_date or minimum.date()
    resolved_end = end_date or maximum.date()
    if resolved_start > resolved_end:
        raise ValueError("startDate must be on or before endDate")
    start_at = datetime.combine(resolved_start, time.min)
    end_at = datetime.combine(resolved_end + timedelta(days=1), time.min)
    trips = list(session.scalars(
        select(Trip)
        .where(Trip.scheduled_arrival >= start_at, Trip.scheduled_arrival < end_at)
        .order_by(Trip.scheduled_arrival)
    ))

    vendor_groups: dict[str, list[Trip]] = defaultdict(list)
    shift_groups: dict[str, list[Trip]] = defaultdict(list)
    week_groups: dict[date, list[Trip]] = defaultdict(list)
    for trip in trips:
        vendor_groups[trip.vendor_id].append(trip)
        shift_groups[trip.shift_id].append(trip)
        trip_date = trip.scheduled_arrival.date()
        week_groups[trip_date - timedelta(days=trip_date.weekday())].append(trip)

    vendor_performance = [
        {"vendorId": vendor_id, **_performance(group, settings)}
        for vendor_id, group in vendor_groups.items()
    ]
    vendor_performance.sort(key=lambda row: (row["ota"] is None, row["ota"] if row["ota"] is not None else 101, -row["completedTrips"]))

    shift_performance = [
        {"shiftId": shift_id, **_performance(group, settings)}
        for shift_id, group in shift_groups.items()
    ]
    shift_performance.sort(key=lambda row: (row["ota"] is None, row["ota"] if row["ota"] is not None else 101))

    weekly_trend = []
    previous_ota: float | None = None
    for week_start, group in sorted(week_groups.items()):
        result = _performance(group, settings)
        ota = result["ota"]
        weekly_trend.append({
            "weekStart": week_start.isoformat(),
            **result,
            "changePoints": round(ota - previous_ota, 2) if ota is not None and previous_ota is not None else None,
        })
        if ota is not None:
            previous_ota = ota

    return {
        "availableRange": {"startDate": minimum.date().isoformat(), "endDate": maximum.date().isoformat()},
        "selectedRange": {"startDate": resolved_start.isoformat(), "endDate": resolved_end.isoformat()},
        "summary": _performance(trips, settings),
        "vendorPerformance": vendor_performance[:8],
        "shiftPerformance": shift_performance[:8],
        "weeklyTrend": weekly_trend,
    }


def get_incident_trip_evidence(
    session: Session,
    settings: Settings,
    incident_id: int,
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any] | None:
    incident = session.get(Incident, incident_id)
    if incident is None:
        return None
    query = select(Trip).where(Trip.status == "completed", Trip.actual_arrival.is_not(None))
    if incident.incident_type.startswith("vendor_ota_below_sla:"):
        vendor_id = incident.contributing_vendor or incident.incident_type.split(":", 1)[1]
        query = query.where(Trip.vendor_id == vendor_id)
    trips = list(session.scalars(query.order_by(Trip.scheduled_arrival.desc())))
    if incident.incident_type == "gps_availability_below_sla":
        matching = [trip for trip in trips if trip.gps_available is False]
    else:
        matching = [trip for trip in trips if _is_delayed(trip, settings)]
    matching.sort(key=_delay_minutes, reverse=True)
    start = (page - 1) * page_size
    page_trips = matching[start:start + page_size]
    return {
        "totalTrips": len(matching),
        "page": page,
        "pageSize": page_size,
        "totalPages": max(1, (len(matching) + page_size - 1) // page_size),
        "trips": [
            {
                "tripId": trip.trip_id,
                "scheduledArrival": trip.scheduled_arrival.isoformat(),
                "vendorId": trip.vendor_id,
                "routeId": trip.route_id,
                "shiftId": trip.shift_id,
                "employeeCount": trip.employee_count,
                "delayMinutes": round(_delay_minutes(trip), 2),
                "delayReason": trip.delay_reason,
                "issue": "GPS unavailable" if incident.incident_type == "gps_availability_below_sla" else f"{_delay_minutes(trip):g} min late",
            }
            for trip in page_trips
        ],
    }
