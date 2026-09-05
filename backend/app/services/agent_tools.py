import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import SafetyAlert, Trip, TripFeedback


DATE_PROPERTIES = {
    "start_date": {
        "type": "string",
        "description": "Optional inclusive start date in YYYY-MM-DD format. Omit to use the first date in the dataset.",
    },
    "end_date": {
        "type": "string",
        "description": "Optional inclusive end date in YYYY-MM-DD format. Omit to use the last date in the dataset.",
    },
}


def _tool(name: str, description: str, properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "additionalProperties": False,
            },
        },
    }


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_trip_summary",
            "description": (
                "Get exact trip counts and performance for an inclusive calendar date range. "
                "Use this whenever the user asks about a day, date range, month, or period."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Inclusive start date in YYYY-MM-DD format.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Inclusive end date in YYYY-MM-DD format.",
                    },
                },
                "required": ["start_date", "end_date"],
                "additionalProperties": False,
            },
        },
    },
    _tool(
        "get_zero_delay_dates",
        "List dates that had trips but zero delayed trips. Use for questions asking which days had no delays.",
        DATE_PROPERTIES,
    ),
    _tool(
        "get_highest_delay_days",
        "Rank the worst dates by delayed-trip count, average delay, or maximum delay.",
        {
            **DATE_PROPERTIES,
            "sort_by": {
                "type": "string",
                "enum": ["delayed_trips", "average_delay", "maximum_delay"],
                "description": "Metric used to rank dates. Defaults to delayed_trips.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 31,
                "description": "Maximum dates to return. Defaults to 5.",
            },
        },
    ),
    _tool(
        "get_vendor_performance",
        "Compare vendors for a date range and rank the lowest on-time arrival performers first.",
        {**DATE_PROPERTIES, "limit": {"type": "integer", "minimum": 1, "maximum": 25}},
    ),
    _tool(
        "get_route_performance",
        "Compare routes for a date range and rank the lowest on-time arrival performers first.",
        {**DATE_PROPERTIES, "limit": {"type": "integer", "minimum": 1, "maximum": 25}},
    ),
    _tool(
        "get_shift_performance",
        "Compare shifts for a date range and rank the lowest on-time arrival performers first.",
        {**DATE_PROPERTIES, "limit": {"type": "integer", "minimum": 1, "maximum": 25}},
    ),
]

LIMIT_PROPERTY = {
    "type": "integer",
    "minimum": 1,
    "maximum": 100,
    "description": "Maximum records to return. Defaults to 20.",
}
TRIP_FILTER_PROPERTIES = {
    **DATE_PROPERTIES,
    "vendor_id": {"type": "string"},
    "office_id": {"type": "string"},
    "shift_id": {"type": "string"},
    "limit": LIMIT_PROPERTY,
}

AGENT_TOOLS.extend([
    _tool("get_trip_details", "List bounded trip-level records for a date range and optional vendor, office, or shift.", TRIP_FILTER_PROPERTIES),
    _tool("get_trip_delays", "List delayed trips with delay minutes and reason for a date range and optional vendor, office, or shift.", TRIP_FILTER_PROPERTIES),
    _tool("get_trip_statistics", "Calculate authoritative trip, delay, employee, no-show, and OTA statistics for a period.", DATE_PROPERTIES),
    _tool("get_delay_by_vendor", "Rank vendors by delayed-trip count for a period.", {**DATE_PROPERTIES, "limit": LIMIT_PROPERTY}),
    _tool("get_delay_by_office", "Rank offices by delayed-trip count for a period.", {**DATE_PROPERTIES, "limit": LIMIT_PROPERTY}),
    _tool("get_delay_by_shift", "Rank shifts by delayed-trip count for a period.", {**DATE_PROPERTIES, "limit": LIMIT_PROPERTY}),
    _tool(
        "compare_vendor_performance",
        "Compare specific vendors using trip count, delays, OTA, no-shows, safety alerts, and ratings.",
        {
            **DATE_PROPERTIES,
            "vendor_ids": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 10},
        },
    ),
    _tool(
        "get_vendor_trips",
        "List trips operated by one vendor for a period.",
        {**DATE_PROPERTIES, "vendor_id": {"type": "string"}, "limit": LIMIT_PROPERTY},
    ),
    _tool(
        "get_vendor_issues",
        "Summarize delay reasons, non-compliance, missing GPS, safety alerts, and low ratings for one vendor.",
        {**DATE_PROPERTIES, "vendor_id": {"type": "string"}},
    ),
    _tool("get_safety_alerts", "List safety alerts with optional date, vendor, office, shift, severity, and state filters.", {
        **TRIP_FILTER_PROPERTIES,
        "severity": {"type": "string"},
        "state": {"type": "string"},
    }),
    _tool("get_alert_details", "Get one safety alert by its event ID, including trip, vendor, office, shift, and acknowledgement data.", {
        "event_id": {"type": "string"},
    }),
    _tool("get_alerts_by_vendor", "Rank vendors by safety-alert count for a period.", {**DATE_PROPERTIES, "limit": LIMIT_PROPERTY}),
    _tool("get_alerts_by_office", "Rank offices by safety-alert count for a period.", {**DATE_PROPERTIES, "limit": LIMIT_PROPERTY}),
    _tool("get_alerts_by_shift", "Rank shifts by safety-alert count for a period.", {**DATE_PROPERTIES, "limit": LIMIT_PROPERTY}),
    _tool("get_employee_impact", "Summarize employees affected by delays, no-shows, and safety alerts for a period.", DATE_PROPERTIES),
    _tool("get_no_show_statistics", "Calculate trip and employee no-show statistics for a period.", DATE_PROPERTIES),
    _tool("get_no_show_by_shift", "Rank shifts by employee no-show count for a period.", {**DATE_PROPERTIES, "limit": LIMIT_PROPERTY}),
    _tool("get_no_show_by_office", "Rank offices by employee no-show count for a period.", {**DATE_PROPERTIES, "limit": LIMIT_PROPERTY}),
    _tool("get_feedback_summary", "Summarize route, driver, cab, safety, and marshal ratings for a period.", DATE_PROPERTIES),
    _tool("get_feedback_by_vendor", "Compare feedback ratings by vendor for a period.", {**DATE_PROPERTIES, "limit": LIMIT_PROPERTY}),
    _tool("get_feedback_by_office", "Compare feedback ratings by office for a period.", {**DATE_PROPERTIES, "limit": LIMIT_PROPERTY}),
    _tool("get_historical_comparison", "Compare a period with the immediately preceding period of equal length.", DATE_PROPERTIES),
    _tool("compare_periods", "Compare two explicit inclusive periods using trip, delay, OTA, no-show, safety, and feedback metrics.", {
        "first_start_date": {"type": "string"},
        "first_end_date": {"type": "string"},
        "second_start_date": {"type": "string"},
        "second_end_date": {"type": "string"},
    }),
    _tool("get_peer_comparison", "Check for external peer benchmark data and compare it with SHLOK performance when available.", DATE_PROPERTIES),
])


def _resolve_range(
    session: Session,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date] | None:
    minimum, maximum = session.execute(
        select(func.min(Trip.scheduled_arrival), func.max(Trip.scheduled_arrival))
    ).one()
    if minimum is None or maximum is None:
        return None
    resolved_start = start_date or minimum.date()
    resolved_end = end_date or maximum.date()
    if resolved_end < resolved_start:
        raise ValueError("end_date must be on or after start_date")
    if (resolved_end - resolved_start).days > 366:
        raise ValueError("date range cannot exceed 366 days")
    return resolved_start, resolved_end


def _trips_in_range(
    session: Session,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date | None, date | None, list[Trip]]:
    resolved = _resolve_range(session, start_date, end_date)
    if resolved is None:
        return None, None, []
    resolved_start, resolved_end = resolved
    start_at = datetime.combine(resolved_start, time.min)
    end_before = datetime.combine(resolved_end + timedelta(days=1), time.min)
    trips = list(session.scalars(select(Trip).where(
        Trip.scheduled_arrival >= start_at,
        Trip.scheduled_arrival < end_before,
    )))
    return resolved_start, resolved_end, trips


def _delay_minutes(trip: Trip) -> float | None:
    if trip.actual_arrival is None:
        return None
    return max((trip.actual_arrival - trip.scheduled_arrival).total_seconds() / 60, 0)


def _is_delayed(trip: Trip, settings: Settings) -> bool:
    delay = _delay_minutes(trip)
    return trip.status == "completed" and delay is not None and delay > settings.ota_grace_minutes


def get_trip_summary(
    session: Session,
    settings: Settings,
    start_date: date,
    end_date: date,
) -> dict[str, object]:
    _, _, trips = _trips_in_range(session, start_date, end_date)
    completed = [trip for trip in trips if trip.status == "completed"]
    delayed = [trip for trip in completed if _is_delayed(trip, settings)]
    return {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dateRangeInclusive": True,
        "totalTrips": len(trips),
        "completedTrips": len(completed),
        "delayedTrips": len(delayed),
        "onTimeTrips": len(completed) - len(delayed),
        "affectedEmployees": sum(trip.employee_count for trip in delayed),
        "ota": round(((len(completed) - len(delayed)) / len(completed)) * 100, 2) if completed else None,
        "otaSla": settings.ota_sla,
    }


def get_zero_delay_dates(
    session: Session,
    settings: Settings,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, object]:
    resolved_start, resolved_end, trips = _trips_in_range(session, start_date, end_date)
    daily: dict[date, list[Trip]] = defaultdict(list)
    for trip in trips:
        daily[trip.scheduled_arrival.date()].append(trip)
    dates = [
        {
            "date": day.isoformat(),
            "totalTrips": len(day_trips),
            "completedTrips": sum(trip.status == "completed" for trip in day_trips),
        }
        for day, day_trips in sorted(daily.items())
        if not any(_is_delayed(trip, settings) for trip in day_trips)
    ]
    return {
        "startDate": resolved_start.isoformat() if resolved_start else None,
        "endDate": resolved_end.isoformat() if resolved_end else None,
        "definition": "Dates with at least one trip and zero completed trips beyond the delay grace period.",
        "count": len(dates),
        "dates": dates,
    }


def get_highest_delay_days(
    session: Session,
    settings: Settings,
    start_date: date | None = None,
    end_date: date | None = None,
    sort_by: Literal["delayed_trips", "average_delay", "maximum_delay"] = "delayed_trips",
    limit: int = 5,
) -> dict[str, object]:
    if sort_by not in {"delayed_trips", "average_delay", "maximum_delay"}:
        raise ValueError("sort_by must be delayed_trips, average_delay, or maximum_delay")
    if not 1 <= limit <= 31:
        raise ValueError("limit must be between 1 and 31")
    resolved_start, resolved_end, trips = _trips_in_range(session, start_date, end_date)
    daily: dict[date, list[Trip]] = defaultdict(list)
    for trip in trips:
        daily[trip.scheduled_arrival.date()].append(trip)
    rows = []
    for day, day_trips in daily.items():
        delayed = [trip for trip in day_trips if _is_delayed(trip, settings)]
        delays = [_delay_minutes(trip) for trip in delayed]
        rows.append({
            "date": day.isoformat(),
            "totalTrips": len(day_trips),
            "delayedTrips": len(delayed),
            "affectedEmployees": sum(trip.employee_count for trip in delayed),
            "averageDelayMinutes": round(sum(delays) / len(delays), 2) if delays else 0.0,
            "maximumDelayMinutes": round(max(delays), 2) if delays else 0.0,
        })
    key = {
        "delayed_trips": "delayedTrips",
        "average_delay": "averageDelayMinutes",
        "maximum_delay": "maximumDelayMinutes",
    }[sort_by]
    rows.sort(key=lambda row: (row[key], row["date"]), reverse=True)
    return {
        "startDate": resolved_start.isoformat() if resolved_start else None,
        "endDate": resolved_end.isoformat() if resolved_end else None,
        "rankedBy": sort_by,
        "days": rows[:limit],
    }


def get_dimension_performance(
    session: Session,
    settings: Settings,
    dimension: Literal["vendor", "route", "shift"],
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 10,
) -> dict[str, object]:
    if not 1 <= limit <= 25:
        raise ValueError("limit must be between 1 and 25")
    resolved_start, resolved_end, trips = _trips_in_range(session, start_date, end_date)
    attribute = {"vendor": "vendor_id", "route": "route_id", "shift": "shift_id"}[dimension]
    groups: dict[str, list[Trip]] = defaultdict(list)
    for trip in trips:
        groups[getattr(trip, attribute)].append(trip)
    rows = []
    for name, group_trips in groups.items():
        completed = [trip for trip in group_trips if trip.status == "completed"]
        delayed = [trip for trip in completed if _is_delayed(trip, settings)]
        ota = round(((len(completed) - len(delayed)) / len(completed)) * 100, 2) if completed else None
        rows.append({
            f"{dimension}Id": name,
            "totalTrips": len(group_trips),
            "completedTrips": len(completed),
            "delayedTrips": len(delayed),
            "affectedEmployees": sum(trip.employee_count for trip in delayed),
            "ota": ota,
        })
    rows.sort(key=lambda row: (row["ota"] is None, row["ota"] if row["ota"] is not None else 101))
    return {
        "startDate": resolved_start.isoformat() if resolved_start else None,
        "endDate": resolved_end.isoformat() if resolved_end else None,
        "rankedBy": "lowest_ota",
        f"{dimension}s": rows[:limit],
    }


def _range_metadata(start_date: date | None, end_date: date | None) -> dict[str, str | None]:
    return {
        "startDate": start_date.isoformat() if start_date else None,
        "endDate": end_date.isoformat() if end_date else None,
    }


def _filter_trips(trips: list[Trip], payload: dict[str, object]) -> list[Trip]:
    filters = {
        "vendor_id": "vendor_id",
        "office_id": "office_id",
        "shift_id": "shift_id",
    }
    for argument, attribute in filters.items():
        if requested := payload.get(argument):
            trips = [
                trip for trip in trips
                if (getattr(trip, attribute) or "").lower() == str(requested).lower()
            ]
    return trips


def _trip_record(trip: Trip, settings: Settings) -> dict[str, object]:
    return {
        "tripId": trip.trip_id,
        "date": trip.scheduled_arrival.date().isoformat(),
        "scheduledArrival": trip.scheduled_arrival.isoformat(),
        "actualArrival": trip.actual_arrival.isoformat() if trip.actual_arrival else None,
        "delayMinutes": round(_delay_minutes(trip) or 0, 2),
        "isDelayed": _is_delayed(trip, settings),
        "delayReason": trip.delay_reason,
        "vendorId": trip.vendor_id,
        "officeId": trip.office_id,
        "shiftId": trip.shift_id,
        "employeeCount": trip.employee_count,
        "noShowCount": trip.no_show_count,
        "status": trip.status,
    }


def _trip_list(
    session: Session,
    settings: Settings,
    payload: dict[str, object],
    delayed_only: bool = False,
) -> dict[str, object]:
    start_date, end_date = _payload_dates(payload)
    resolved_start, resolved_end, trips = _trips_in_range(session, start_date, end_date)
    trips = _filter_trips(trips, payload)
    if delayed_only:
        trips = [trip for trip in trips if _is_delayed(trip, settings)]
        trips.sort(key=lambda trip: _delay_minutes(trip) or 0, reverse=True)
    else:
        trips.sort(key=lambda trip: trip.scheduled_arrival)
    limit = _limit(payload)
    return {
        **_range_metadata(resolved_start, resolved_end),
        "matchingTrips": len(trips),
        "returnedTrips": min(len(trips), limit),
        "truncated": len(trips) > limit,
        "trips": [_trip_record(trip, settings) for trip in trips[:limit]],
    }


def _delay_by_dimension(
    session: Session,
    settings: Settings,
    payload: dict[str, object],
    dimension: Literal["vendor", "office", "shift"],
) -> dict[str, object]:
    start_date, end_date = _payload_dates(payload)
    resolved_start, resolved_end, trips = _trips_in_range(session, start_date, end_date)
    attribute = {"vendor": "vendor_id", "office": "office_id", "shift": "shift_id"}[dimension]
    groups: dict[str, list[Trip]] = defaultdict(list)
    for trip in trips:
        groups[getattr(trip, attribute) or "Unknown"].append(trip)
    rows = []
    for name, group_trips in groups.items():
        delayed = [trip for trip in group_trips if _is_delayed(trip, settings)]
        rows.append({
            f"{dimension}Id": name,
            "totalTrips": len(group_trips),
            "delayedTrips": len(delayed),
            "affectedEmployees": sum(trip.employee_count for trip in delayed),
            "averageDelayMinutes": round(
                sum(_delay_minutes(trip) or 0 for trip in delayed) / len(delayed), 2
            ) if delayed else 0.0,
        })
    rows.sort(key=lambda row: (row["delayedTrips"], row["averageDelayMinutes"]), reverse=True)
    return {
        **_range_metadata(resolved_start, resolved_end),
        "rankedBy": "delayed_trips",
        f"{dimension}s": rows[:_limit(payload)],
    }


def _joined_alerts(
    session: Session,
    payload: dict[str, object],
) -> tuple[date | None, date | None, list[tuple[SafetyAlert, Trip]]]:
    start_date, end_date = _payload_dates(payload)
    resolved_start, resolved_end, trips = _trips_in_range(session, start_date, end_date)
    trip_map = {trip.trip_id: trip for trip in _filter_trips(trips, payload)}
    if not trip_map:
        return resolved_start, resolved_end, []
    alerts = list(session.scalars(select(SafetyAlert).where(SafetyAlert.trip_id.in_(trip_map))))
    joined = [(alert, trip_map[alert.trip_id]) for alert in alerts]
    if severity := payload.get("severity"):
        joined = [row for row in joined if (row[0].severity or "").lower() == str(severity).lower()]
    if state := payload.get("state"):
        joined = [row for row in joined if row[0].state.lower() == str(state).lower()]
    joined.sort(key=lambda row: row[0].started_at, reverse=True)
    return resolved_start, resolved_end, joined


def _alert_record(alert: SafetyAlert, trip: Trip) -> dict[str, object]:
    acknowledgement_minutes = None
    if alert.acknowledged_at:
        acknowledgement_minutes = round(
            (alert.acknowledged_at - alert.started_at).total_seconds() / 60, 2
        )
    return {
        "eventId": alert.event_id,
        "eventType": alert.event_type,
        "tripId": alert.trip_id,
        "employeeId": alert.employee_id if alert.employee_id != "0" else None,
        "startedAt": alert.started_at.isoformat(),
        "acknowledgedAt": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "acknowledgementMinutes": acknowledgement_minutes,
        "state": alert.state,
        "severity": alert.severity,
        "source": alert.source,
        "vendorId": trip.vendor_id,
        "officeId": trip.office_id,
        "shiftId": trip.shift_id,
    }


def _alerts_by_dimension(
    session: Session,
    payload: dict[str, object],
    dimension: Literal["vendor", "office", "shift"],
) -> dict[str, object]:
    resolved_start, resolved_end, joined = _joined_alerts(session, payload)
    attribute = {"vendor": "vendor_id", "office": "office_id", "shift": "shift_id"}[dimension]
    groups: dict[str, list[SafetyAlert]] = defaultdict(list)
    for alert, trip in joined:
        groups[getattr(trip, attribute) or "Unknown"].append(alert)
    rows = [{
        f"{dimension}Id": name,
        "totalAlerts": len(alerts),
        "openAlerts": sum(alert.state.upper() in {"OPEN", "NEW"} for alert in alerts),
        "severity1Alerts": sum(alert.severity == "Sev-1" for alert in alerts),
        "unacknowledgedAlerts": sum(alert.acknowledged_at is None for alert in alerts),
    } for name, alerts in groups.items()]
    rows.sort(key=lambda row: (row["totalAlerts"], row["openAlerts"]), reverse=True)
    return {
        **_range_metadata(resolved_start, resolved_end),
        f"{dimension}s": rows[:_limit(payload)],
    }


def _no_shows_by_dimension(
    session: Session,
    payload: dict[str, object],
    dimension: Literal["office", "shift"],
) -> dict[str, object]:
    start_date, end_date = _payload_dates(payload)
    resolved_start, resolved_end, trips = _trips_in_range(session, start_date, end_date)
    attribute = {"office": "office_id", "shift": "shift_id"}[dimension]
    groups: dict[str, list[Trip]] = defaultdict(list)
    for trip in trips:
        groups[getattr(trip, attribute) or "Unknown"].append(trip)
    rows = [{
        f"{dimension}Id": name,
        "totalTrips": len(group_trips),
        "tripsWithNoShows": sum(trip.no_show_count > 0 for trip in group_trips),
        "noShowEmployees": sum(trip.no_show_count for trip in group_trips),
    } for name, group_trips in groups.items()]
    rows.sort(key=lambda row: row["noShowEmployees"], reverse=True)
    return {
        **_range_metadata(resolved_start, resolved_end),
        f"{dimension}s": rows[:_limit(payload)],
    }


def _joined_feedback(
    session: Session,
    payload: dict[str, object],
) -> tuple[date | None, date | None, list[tuple[TripFeedback, Trip]]]:
    start_date, end_date = _payload_dates(payload)
    resolved_start, resolved_end, trips = _trips_in_range(session, start_date, end_date)
    trip_map = {trip.trip_id: trip for trip in _filter_trips(trips, payload)}
    if not trip_map:
        return resolved_start, resolved_end, []
    feedback = list(session.scalars(select(TripFeedback).where(TripFeedback.trip_id.in_(trip_map))))
    return resolved_start, resolved_end, [(item, trip_map[item.trip_id]) for item in feedback]


def _rating_summary(feedback: list[TripFeedback]) -> dict[str, object]:
    result: dict[str, object] = {"responses": len(feedback)}
    for label, attribute in {
        "route": "route_rating",
        "driver": "driver_rating",
        "cab": "cab_rating",
        "safety": "safety_rating",
        "marshal": "marshal_rating",
    }.items():
        ratings = [getattr(item, attribute) for item in feedback if getattr(item, attribute) > 0]
        result[f"{label}Average"] = round(sum(ratings) / len(ratings), 2) if ratings else None
        result[f"{label}RatedResponses"] = len(ratings)
    result["zeroRatingsExcludedFromAverages"] = True
    return result


def _feedback_by_dimension(
    session: Session,
    payload: dict[str, object],
    dimension: Literal["vendor", "office"],
) -> dict[str, object]:
    resolved_start, resolved_end, joined = _joined_feedback(session, payload)
    attribute = {"vendor": "vendor_id", "office": "office_id"}[dimension]
    groups: dict[str, list[TripFeedback]] = defaultdict(list)
    for feedback, trip in joined:
        groups[getattr(trip, attribute) or "Unknown"].append(feedback)
    rows = [{f"{dimension}Id": name, **_rating_summary(items)} for name, items in groups.items()]
    rows.sort(key=lambda row: row["responses"], reverse=True)
    return {
        **_range_metadata(resolved_start, resolved_end),
        f"{dimension}s": rows[:_limit(payload)],
    }


def _payload_dates(payload: dict[str, object]) -> tuple[date | None, date | None]:
    start = date.fromisoformat(str(payload["start_date"])) if payload.get("start_date") else None
    end = date.fromisoformat(str(payload["end_date"])) if payload.get("end_date") else None
    return start, end


def _limit(payload: dict[str, object], default: int = 20) -> int:
    limit = int(payload.get("limit", default))
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    return limit


def _period_snapshot(
    session: Session,
    settings: Settings,
    start_date: date,
    end_date: date,
) -> dict[str, object]:
    summary = get_trip_summary(session, settings, start_date, end_date)
    payload: dict[str, object] = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    _, _, alerts = _joined_alerts(session, payload)
    _, _, feedback = _joined_feedback(session, payload)
    return {
        **summary,
        "noShowEmployees": sum(
            trip.no_show_count for _, _, trips in [_trips_in_range(session, start_date, end_date)] for trip in trips
        ),
        "safetyAlerts": len(alerts),
        "feedback": _rating_summary([item for item, _ in feedback]),
    }


def execute_agent_tool(
    session: Session,
    settings: Settings,
    name: str,
    arguments: str,
) -> dict[str, object]:
    payload = json.loads(arguments)
    start_date, end_date = _payload_dates(payload)
    if name == "get_trip_summary":
        if start_date is None or end_date is None:
            raise ValueError("get_trip_summary requires start_date and end_date")
        return get_trip_summary(session, settings, start_date, end_date)
    if name == "get_zero_delay_dates":
        return get_zero_delay_dates(session, settings, start_date, end_date)
    if name == "get_highest_delay_days":
        return get_highest_delay_days(
            session,
            settings,
            start_date,
            end_date,
            payload.get("sort_by", "delayed_trips"),
            payload.get("limit", 5),
        )
    if name in {"get_trip_details", "get_vendor_trips"}:
        if name == "get_vendor_trips":
            if not payload.get("vendor_id"):
                raise ValueError("get_vendor_trips requires vendor_id")
        return _trip_list(session, settings, payload)
    if name == "get_trip_delays":
        return _trip_list(session, settings, payload, delayed_only=True)
    if name == "get_trip_statistics":
        resolved = _resolve_range(session, start_date, end_date)
        if resolved is None:
            return {"startDate": None, "endDate": None, "totalTrips": 0}
        resolved_start, resolved_end = resolved
        summary = get_trip_summary(session, settings, resolved_start, resolved_end)
        _, _, trips = _trips_in_range(session, resolved_start, resolved_end)
        delayed = [trip for trip in trips if _is_delayed(trip, settings)]
        delay_values = [_delay_minutes(trip) or 0 for trip in delayed]
        return {
            **summary,
            "averageDelayMinutes": round(sum(delay_values) / len(delay_values), 2) if delay_values else 0.0,
            "maximumDelayMinutes": round(max(delay_values), 2) if delay_values else 0.0,
            "noShowEmployees": sum(trip.no_show_count for trip in trips),
        }
    delay_dimensions = {
        "get_delay_by_vendor": "vendor",
        "get_delay_by_office": "office",
        "get_delay_by_shift": "shift",
    }
    if dimension := delay_dimensions.get(name):
        return _delay_by_dimension(session, settings, payload, dimension)
    dimensions = {
        "get_vendor_performance": "vendor",
        "get_route_performance": "route",
        "get_shift_performance": "shift",
    }
    if dimension := dimensions.get(name):
        return get_dimension_performance(
            session,
            settings,
            dimension,
            start_date,
            end_date,
            payload.get("limit", 10),
        )
    if name == "compare_vendor_performance":
        vendor_ids = payload.get("vendor_ids")
        if not isinstance(vendor_ids, list) or len(vendor_ids) < 2:
            raise ValueError("compare_vendor_performance requires at least two vendor_ids")
        performance = get_dimension_performance(session, settings, "vendor", start_date, end_date, 25)
        requested = {str(vendor_id).lower() for vendor_id in vendor_ids}
        vendors = [
            row for row in performance["vendors"]
            if str(row["vendorId"]).lower() in requested
        ]
        alert_result = _alerts_by_dimension(session, payload, "vendor")
        feedback_result = _feedback_by_dimension(session, payload, "vendor")
        alerts = {row["vendorId"]: row for row in alert_result["vendors"]}
        feedback = {row["vendorId"]: row for row in feedback_result["vendors"]}
        for vendor in vendors:
            vendor["safetyAlerts"] = alerts.get(vendor["vendorId"], {}).get("totalAlerts", 0)
            vendor["feedback"] = feedback.get(vendor["vendorId"])
        return {
            "startDate": performance["startDate"],
            "endDate": performance["endDate"],
            "vendors": vendors,
            "notFound": [vendor_id for vendor_id in vendor_ids if str(vendor_id).lower() not in {
                str(row["vendorId"]).lower() for row in vendors
            }],
        }
    if name == "get_vendor_issues":
        vendor_id = payload.get("vendor_id")
        if not vendor_id:
            raise ValueError("get_vendor_issues requires vendor_id")
        resolved_start, resolved_end, trips = _trips_in_range(session, start_date, end_date)
        trips = _filter_trips(trips, payload)
        delayed = [trip for trip in trips if _is_delayed(trip, settings)]
        reasons = Counter(trip.delay_reason or "Unknown" for trip in delayed)
        _, _, alerts = _joined_alerts(session, payload)
        _, _, feedback = _joined_feedback(session, payload)
        feedback_items = [item for item, _ in feedback]
        return {
            **_range_metadata(resolved_start, resolved_end),
            "vendorId": vendor_id,
            "totalTrips": len(trips),
            "delayedTrips": len(delayed),
            "delayReasons": dict(reasons.most_common()),
            "driverNonComplianceTrips": sum(trip.driver_non_compliance is True for trip in trips),
            "cabNonComplianceTrips": sum(trip.cab_non_compliance is True for trip in trips),
            "missingGpsTrips": sum(trip.gps_available is False for trip in trips),
            "safetyAlerts": len(alerts),
            "openSafetyAlerts": sum(alert.state.upper() in {"OPEN", "NEW"} for alert, _ in alerts),
            "feedback": _rating_summary(feedback_items),
        }
    if name == "get_safety_alerts":
        resolved_start, resolved_end, joined = _joined_alerts(session, payload)
        limit = _limit(payload)
        return {
            **_range_metadata(resolved_start, resolved_end),
            "matchingAlerts": len(joined),
            "returnedAlerts": min(len(joined), limit),
            "truncated": len(joined) > limit,
            "alerts": [_alert_record(alert, trip) for alert, trip in joined[:limit]],
        }
    if name == "get_alert_details":
        event_id = payload.get("event_id")
        if not event_id:
            raise ValueError("get_alert_details requires event_id")
        row = session.execute(
            select(SafetyAlert, Trip)
            .join(Trip, Trip.trip_id == SafetyAlert.trip_id)
            .where(SafetyAlert.event_id == str(event_id))
        ).one_or_none()
        return {"found": row is not None, "alert": _alert_record(*row) if row else None}
    alert_dimensions = {
        "get_alerts_by_vendor": "vendor",
        "get_alerts_by_office": "office",
        "get_alerts_by_shift": "shift",
    }
    if dimension := alert_dimensions.get(name):
        return _alerts_by_dimension(session, payload, dimension)
    if name in {"get_employee_impact", "get_no_show_statistics"}:
        resolved_start, resolved_end, trips = _trips_in_range(session, start_date, end_date)
        delayed = [trip for trip in trips if _is_delayed(trip, settings)]
        result = {
            **_range_metadata(resolved_start, resolved_end),
            "totalTrips": len(trips),
            "tripsWithNoShows": sum(trip.no_show_count > 0 for trip in trips),
            "noShowEmployees": sum(trip.no_show_count for trip in trips),
        }
        if name == "get_employee_impact":
            _, _, alerts = _joined_alerts(session, payload)
            result.update({
                "employeesOnDelayedTrips": sum(trip.employee_count for trip in delayed),
                "delayedTrips": len(delayed),
                "employeesLinkedToSafetyAlerts": len({
                    alert.employee_id for alert, _ in alerts if alert.employee_id not in {None, "0"}
                }),
            })
        return result
    no_show_dimensions = {
        "get_no_show_by_shift": "shift",
        "get_no_show_by_office": "office",
    }
    if dimension := no_show_dimensions.get(name):
        return _no_shows_by_dimension(session, payload, dimension)
    if name == "get_feedback_summary":
        resolved_start, resolved_end, joined = _joined_feedback(session, payload)
        return {
            **_range_metadata(resolved_start, resolved_end),
            **_rating_summary([item for item, _ in joined]),
        }
    feedback_dimensions = {
        "get_feedback_by_vendor": "vendor",
        "get_feedback_by_office": "office",
    }
    if dimension := feedback_dimensions.get(name):
        return _feedback_by_dimension(session, payload, dimension)
    if name == "get_historical_comparison":
        resolved = _resolve_range(session, start_date, end_date)
        if resolved is None:
            return {"currentPeriod": None, "previousPeriod": None}
        current_start, current_end = resolved
        if start_date is None and end_date is None:
            current_start = max(current_start, current_end - timedelta(days=29))
        period_days = (current_end - current_start).days + 1
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=period_days - 1)
        return {
            "currentPeriod": _period_snapshot(session, settings, current_start, current_end),
            "previousPeriod": _period_snapshot(session, settings, previous_start, previous_end),
        }
    if name == "compare_periods":
        required = ["first_start_date", "first_end_date", "second_start_date", "second_end_date"]
        if any(not payload.get(field) for field in required):
            raise ValueError("compare_periods requires both start and end dates for both periods")
        first_start = date.fromisoformat(str(payload["first_start_date"]))
        first_end = date.fromisoformat(str(payload["first_end_date"]))
        second_start = date.fromisoformat(str(payload["second_start_date"]))
        second_end = date.fromisoformat(str(payload["second_end_date"]))
        return {
            "firstPeriod": _period_snapshot(session, settings, first_start, first_end),
            "secondPeriod": _period_snapshot(session, settings, second_start, second_end),
        }
    if name == "get_peer_comparison":
        return {
            "available": False,
            "reason": "No external peer benchmark dataset is loaded.",
            "requiredData": ["peer identifier", "period", "trip volume", "OTA", "delay metrics"],
        }
    raise ValueError(f"Unknown agent tool: {name}")
