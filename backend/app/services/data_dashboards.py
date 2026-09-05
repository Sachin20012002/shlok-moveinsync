import csv
import io
from collections.abc import Iterable, Iterator
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Select, and_, case, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import SafetyAlert, Trip, TripFeedback


PAGE_SIZE_MAX = 100
FACET_LIMIT = 200


def _date_bounds(start_date: date | None, end_date: date | None) -> tuple[datetime | None, datetime | None]:
    return (
        datetime.combine(start_date, time.min) if start_date else None,
        datetime.combine(end_date + timedelta(days=1), time.min) if end_date else None,
    )


def _date_filters(column: Any, start_date: date | None, end_date: date | None) -> list[Any]:
    start, end = _date_bounds(start_date, end_date)
    filters: list[Any] = []
    if start is not None:
        filters.append(column >= start)
    if end is not None:
        filters.append(column < end)
    return filters


def _delay_expression(session: Session) -> Any:
    if session.get_bind().dialect.name == "postgresql":
        inferred = func.extract("epoch", Trip.actual_arrival - Trip.scheduled_arrival) / 60
    else:
        inferred = (func.julianday(Trip.actual_arrival) - func.julianday(Trip.scheduled_arrival)) * 1440
    return func.coalesce(Trip.reported_delay_minutes, inferred)


def _delayed_condition(session: Session, settings: Settings) -> Any:
    inferred_delay = _delay_expression(session)
    return or_(
        Trip.reported_delay_minutes > 0,
        and_(
            Trip.reported_delay_minutes.is_(None),
            Trip.actual_arrival.is_not(None),
            inferred_delay > settings.ota_grace_minutes,
        ),
    )


def _pagination(page: int, page_size: int, total_rows: int) -> dict[str, int]:
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    return {
        "page": page,
        "pageSize": page_size,
        "totalRows": total_rows,
        "totalPages": total_pages,
    }


def _facet(session: Session, column: Any, *filters: Any) -> list[str]:
    query = (
        select(column)
        .where(column.is_not(None), *filters)
        .distinct()
        .order_by(column)
        .limit(FACET_LIMIT)
    )
    return [str(value) for value in session.scalars(query) if str(value).strip()]


def _sort(query: Select[Any], sort: str, direction: str, columns: dict[str, Any], default: str) -> Select[Any]:
    column = columns.get(sort, columns[default])
    return query.order_by(desc(column) if direction == "desc" else column)


def get_trip_dashboard(
    session: Session,
    settings: Settings,
    *,
    page: int,
    page_size: int,
    start_date: date | None = None,
    end_date: date | None = None,
    vendor: str | None = None,
    office: str | None = None,
    shift: str | None = None,
    status: str | None = None,
    delay_reason: str | None = None,
    delayed: bool | None = None,
    driver_nc: bool | None = None,
    cab_nc: bool | None = None,
    sort: str = "scheduledArrival",
    direction: str = "desc",
) -> dict[str, Any]:
    filters = _date_filters(Trip.scheduled_arrival, start_date, end_date)
    for value, column in (
        (vendor, Trip.vendor_id),
        (office, Trip.office_id),
        (shift, Trip.shift_id),
        (status, Trip.status),
        (delay_reason, Trip.delay_reason),
    ):
        if value:
            filters.append(column == value)
    delayed_condition = _delayed_condition(session, settings)
    if delayed is not None:
        filters.append(delayed_condition if delayed else ~delayed_condition)
    if driver_nc is not None:
        filters.append(Trip.driver_non_compliance.is_(driver_nc))
    if cab_nc is not None:
        filters.append(Trip.cab_non_compliance.is_(cab_nc))

    delay_value = _delay_expression(session)
    completed_condition = func.lower(Trip.status) == "completed"
    summary = session.execute(
        select(
            func.count(Trip.id),
            func.count(Trip.id).filter(completed_condition),
            func.count(Trip.id).filter(and_(completed_condition, delayed_condition)),
            func.coalesce(func.sum(Trip.no_show_count), 0),
            func.count(Trip.id).filter(Trip.driver_non_compliance.is_(True)),
            func.count(Trip.id).filter(Trip.cab_non_compliance.is_(True)),
            func.coalesce(
                func.sum(Trip.employee_count).filter(and_(completed_condition, delayed_condition)),
                0,
            ),
        ).where(*filters)
    ).one()
    total_rows = int(summary[0] or 0)
    completed = int(summary[1] or 0)
    delayed_count = int(summary[2] or 0)
    ota = round(((completed - delayed_count) / completed) * 100, 2) if completed else None

    query = select(Trip, delay_value.label("delay_minutes")).where(*filters)
    query = _sort(query, sort, direction, {
        "scheduledArrival": Trip.scheduled_arrival,
        "tripId": Trip.trip_id,
        "vendorId": Trip.vendor_id,
        "officeId": Trip.office_id,
        "shiftId": Trip.shift_id,
        "status": Trip.status,
        "delayMinutes": delay_value,
    }, "scheduledArrival")
    result = session.execute(query.offset((page - 1) * page_size).limit(page_size)).all()
    rows = [
        {
            "tripId": trip.trip_id,
            "scheduledArrival": trip.scheduled_arrival,
            "actualArrival": trip.actual_arrival,
            "vendorId": trip.vendor_id,
            "officeId": trip.office_id,
            "shiftId": trip.shift_id,
            "status": trip.status,
            "employeeCount": trip.employee_count,
            "delayMinutes": round(max(0.0, float(delay_minutes or 0)), 2),
            "delayReason": trip.delay_reason,
            "noShowCount": trip.no_show_count,
            "driverNonCompliance": trip.driver_non_compliance,
            "cabNonCompliance": trip.cab_non_compliance,
        }
        for trip, delay_minutes in result
    ]
    date_only_filters = _date_filters(Trip.scheduled_arrival, start_date, end_date)
    return {
        "summary": {
            "totalTrips": total_rows,
            "completedTrips": completed,
            "delayedTrips": delayed_count,
            "ota": ota,
            "noShows": int(summary[3] or 0),
            "driverNonCompliance": int(summary[4] or 0),
            "cabNonCompliance": int(summary[5] or 0),
            "affectedEmployees": int(summary[6] or 0),
        },
        "facets": {
            "vendors": _facet(session, Trip.vendor_id, *date_only_filters),
            "offices": _facet(session, Trip.office_id, *date_only_filters),
            "shifts": _facet(session, Trip.shift_id, *date_only_filters),
            "statuses": _facet(session, Trip.status, *date_only_filters),
            "delayReasons": _facet(session, Trip.delay_reason, *date_only_filters),
        },
        "rows": rows,
        "pagination": _pagination(page, page_size, total_rows),
    }


def get_feedback_dashboard(
    session: Session,
    *,
    page: int,
    page_size: int,
    start_date: date | None = None,
    end_date: date | None = None,
    vendor: str | None = None,
    office: str | None = None,
    trip_type: str | None = None,
    rating_category: str = "driver",
    max_rating: int | None = None,
    sort: str = "tripAt",
    direction: str = "desc",
) -> dict[str, Any]:
    filters = _date_filters(TripFeedback.trip_at, start_date, end_date)
    if vendor:
        filters.append(Trip.vendor_id == vendor)
    if office:
        filters.append(Trip.office_id == office)
    if trip_type:
        filters.append(TripFeedback.trip_type == trip_type)
    ratings = {
        "route": TripFeedback.route_rating,
        "driver": TripFeedback.driver_rating,
        "cab": TripFeedback.cab_rating,
        "safety": TripFeedback.safety_rating,
        "marshal": TripFeedback.marshal_rating,
    }
    selected_rating = ratings.get(rating_category, TripFeedback.driver_rating)
    if max_rating is not None:
        filters.append(selected_rating <= max_rating)

    base = select(TripFeedback).join(Trip, Trip.trip_id == TripFeedback.trip_id).where(*filters)
    summary = session.execute(
        select(
            func.count(TripFeedback.id),
            func.avg(TripFeedback.route_rating),
            func.avg(TripFeedback.driver_rating),
            func.avg(TripFeedback.cab_rating),
            func.avg(TripFeedback.safety_rating),
            func.count(TripFeedback.id).filter(or_(
                TripFeedback.route_rating <= 2,
                TripFeedback.driver_rating <= 2,
                TripFeedback.cab_rating <= 2,
                TripFeedback.safety_rating <= 2,
            )),
        ).join(Trip, Trip.trip_id == TripFeedback.trip_id).where(*filters)
    ).one()
    total_rows = int(summary[0] or 0)
    query = _sort(base.add_columns(Trip.vendor_id, Trip.office_id), sort, direction, {
        "tripAt": TripFeedback.trip_at,
        "tripId": TripFeedback.trip_id,
        "vendorId": Trip.vendor_id,
        "tripType": TripFeedback.trip_type,
        "routeRating": TripFeedback.route_rating,
        "driverRating": TripFeedback.driver_rating,
        "cabRating": TripFeedback.cab_rating,
        "safetyRating": TripFeedback.safety_rating,
    }, "tripAt")
    result = session.execute(query.offset((page - 1) * page_size).limit(page_size)).all()
    rows = [
        {
            "tripId": item.trip_id,
            "tripAt": item.trip_at,
            "employeeId": item.employee_id,
            "vendorId": vendor_id,
            "officeId": office_id,
            "tripType": item.trip_type,
            "routeRating": item.route_rating,
            "driverRating": item.driver_rating,
            "cabRating": item.cab_rating,
            "safetyRating": item.safety_rating,
            "marshalRating": item.marshal_rating,
        }
        for item, vendor_id, office_id in result
    ]
    date_only_filters = _date_filters(TripFeedback.trip_at, start_date, end_date)
    return {
        "summary": {
            "totalResponses": total_rows,
            "averageRouteRating": round(float(summary[1]), 2) if summary[1] is not None else None,
            "averageDriverRating": round(float(summary[2]), 2) if summary[2] is not None else None,
            "averageCabRating": round(float(summary[3]), 2) if summary[3] is not None else None,
            "averageSafetyRating": round(float(summary[4]), 2) if summary[4] is not None else None,
            "lowRatingCount": int(summary[5] or 0),
        },
        "facets": {
            "vendors": _facet(session, Trip.vendor_id),
            "offices": _facet(session, Trip.office_id),
            "tripTypes": _facet(session, TripFeedback.trip_type, *date_only_filters),
        },
        "rows": rows,
        "pagination": _pagination(page, page_size, total_rows),
    }


def get_alert_dashboard(
    session: Session,
    *,
    page: int,
    page_size: int,
    start_date: date | None = None,
    end_date: date | None = None,
    state: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    vendor: str | None = None,
    office: str | None = None,
    employee: str | None = None,
    source: str | None = None,
    sort: str = "startedAt",
    direction: str = "desc",
) -> dict[str, Any]:
    filters = _date_filters(SafetyAlert.started_at, start_date, end_date)
    for value, column in (
        (state, SafetyAlert.state),
        (severity, SafetyAlert.severity),
        (event_type, SafetyAlert.event_type),
        (vendor, Trip.vendor_id),
        (office, Trip.office_id),
        (employee, SafetyAlert.employee_id),
        (source, SafetyAlert.source),
    ):
        if value:
            filters.append(column == value)
    open_condition = func.upper(SafetyAlert.state).in_(("OPEN", "NEW"))
    critical_condition = func.lower(SafetyAlert.severity) == "critical"
    acknowledged_condition = SafetyAlert.acknowledged_at.is_not(None)
    if session.get_bind().dialect.name == "postgresql":
        response_minutes = func.extract("epoch", SafetyAlert.acknowledged_at - SafetyAlert.started_at) / 60
    else:
        response_minutes = (func.julianday(SafetyAlert.acknowledged_at) - func.julianday(SafetyAlert.started_at)) * 1440
    summary = session.execute(
        select(
            func.count(SafetyAlert.id),
            func.count(SafetyAlert.id).filter(open_condition),
            func.count(SafetyAlert.id).filter(critical_condition),
            func.count(SafetyAlert.id).filter(acknowledged_condition),
            func.avg(response_minutes).filter(acknowledged_condition),
        ).join(Trip, Trip.trip_id == SafetyAlert.trip_id).where(*filters)
    ).one()
    total_rows = int(summary[0] or 0)
    query = select(SafetyAlert, Trip.vendor_id, Trip.office_id, response_minutes.label("response_minutes")).join(
        Trip, Trip.trip_id == SafetyAlert.trip_id
    ).where(*filters)
    query = _sort(query, sort, direction, {
        "startedAt": SafetyAlert.started_at,
        "eventId": SafetyAlert.event_id,
        "tripId": SafetyAlert.trip_id,
        "eventType": SafetyAlert.event_type,
        "severity": SafetyAlert.severity,
        "state": SafetyAlert.state,
        "vendorId": Trip.vendor_id,
    }, "startedAt")
    result = session.execute(query.offset((page - 1) * page_size).limit(page_size)).all()
    rows = [
        {
            "eventId": alert.event_id,
            "tripId": alert.trip_id,
            "startedAt": alert.started_at,
            "eventType": alert.event_type,
            "severity": alert.severity,
            "state": alert.state,
            "employeeId": alert.employee_id,
            "vendorId": vendor_id,
            "officeId": office_id,
            "source": alert.source,
            "acknowledgedAt": alert.acknowledged_at,
            "responseMinutes": round(float(response_minutes), 2) if response_minutes is not None else None,
        }
        for alert, vendor_id, office_id, response_minutes in result
    ]
    date_only_filters = _date_filters(SafetyAlert.started_at, start_date, end_date)
    return {
        "summary": {
            "totalAlerts": total_rows,
            "openAlerts": int(summary[1] or 0),
            "criticalAlerts": int(summary[2] or 0),
            "acknowledgedAlerts": int(summary[3] or 0),
            "averageResponseMinutes": round(float(summary[4]), 2) if summary[4] is not None else None,
        },
        "facets": {
            "states": _facet(session, SafetyAlert.state, *date_only_filters),
            "severities": _facet(session, SafetyAlert.severity, *date_only_filters),
            "eventTypes": _facet(session, SafetyAlert.event_type, *date_only_filters),
            "vendors": _facet(session, Trip.vendor_id),
            "offices": _facet(session, Trip.office_id),
            "sources": _facet(session, SafetyAlert.source, *date_only_filters),
        },
        "rows": rows,
        "pagination": _pagination(page, page_size, total_rows),
    }


def csv_stream(columns: list[tuple[str, str]], rows: Iterable[dict[str, Any]]) -> Iterator[str]:
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow([label for _, label in columns])
    yield stream.getvalue()
    for row in rows:
        stream.seek(0)
        stream.truncate(0)
        writer.writerow([row.get(key) for key, _ in columns])
        yield stream.getvalue()
