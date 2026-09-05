import json
from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.connection import SessionLocal, engine, get_db
from app.database.migrations import migrate_database
from app.database.models import DatasetUpload, Incident, IncidentEvent, MetricSnapshot
from app.schemas.api import DataDashboardResponse, DashboardResponse, IncidentEmailDraftResponse, IncidentEventResponse, IncidentResponse, IncidentTripEvidenceResponse, MobilityAgentRequest, OperationsAnalyticsResponse, OperationsResponse, UploadResponse
from app.services.agent import build_agent_context, stream_agent_response
from app.services.agent_tools import (
    execute_agent_tool,
    get_dimension_performance,
    get_highest_delay_days,
    get_trip_summary,
    get_zero_delay_dates,
)
from app.services.ingestion import ingest_csv
from app.services.detection import evaluate_operations
from app.services.data_dashboards import csv_stream, get_alert_dashboard, get_feedback_dashboard, get_trip_dashboard
from app.services.operations import build_operations_response
from app.services.operations_analytics import get_incident_trip_evidence, get_operations_analytics
from app.services.reference_data import sync_reference_data


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate_database(engine)
    with SessionLocal() as session:
        sync_reference_data(session, settings.reference_data_dir)
        latest_dataset_id = session.scalar(
            select(DatasetUpload.id).order_by(desc(DatasetUpload.id)).limit(1)
        )
        snapshot_exists = latest_dataset_id is not None and session.scalar(
            select(func.count())
            .select_from(MetricSnapshot)
            .where(MetricSnapshot.dataset_upload_id == latest_dataset_id)
        )
        if latest_dataset_id is not None and not snapshot_exists:
            evaluate_operations(session, latest_dataset_id, settings)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "SHLOK MoveInSync backend is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "shlok-moveinsync-backend",
    }


@app.post("/api/datasets/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
def upload_dataset(
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    try:
        upload, incident_created = ingest_csv(
            session,
            file.filename,
            file.file,
            settings,
        )
    except ValueError as error:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    return UploadResponse(
        dataset_id=upload.id,
        filename=upload.filename,
        valid_rows=upload.valid_rows,
        invalid_rows=upload.invalid_rows,
        skipped_rows=upload.skipped_rows,
        incident_created=incident_created,
    )


@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard(session: Session = Depends(get_db)) -> DashboardResponse:
    snapshot = session.scalar(select(MetricSnapshot).order_by(desc(MetricSnapshot.id)).limit(1))
    active_incidents = session.scalar(
        select(func.count()).select_from(Incident).where(Incident.attention_required.is_(True))
    ) or 0
    if snapshot is None:
        return DashboardResponse(
            on_time_arrival={
                "value": None,
                "sla": settings.ota_sla,
                "previousValue": None,
                "status": "insufficient_data",
            },
            completed_trips=0,
            delayed_trips=0,
            affected_employees=0,
            average_delay_minutes=None,
            active_incident_count=active_incidents,
        )
    ota_status = (
        "insufficient_data"
        if snapshot.ota_value is None
        else "critical" if snapshot.ota_value < snapshot.sla_value else "healthy"
    )
    return DashboardResponse(
        on_time_arrival={
            "value": snapshot.ota_value,
            "sla": snapshot.sla_value,
            "previousValue": None,
            "status": ota_status,
        },
        completed_trips=snapshot.completed_trips,
        delayed_trips=snapshot.delayed_trips,
        affected_employees=snapshot.affected_employees,
        average_delay_minutes=snapshot.average_delay_minutes,
        active_incident_count=active_incidents,
    )


@app.get("/api/dashboards/trips", response_model=DataDashboardResponse)
def get_trips_dashboard(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=10, le=100),
    start_date: date | None = Query(None, alias="startDate"),
    end_date: date | None = Query(None, alias="endDate"),
    vendor: str | None = None,
    office: str | None = None,
    shift: str | None = None,
    trip_status: str | None = Query(None, alias="status"),
    delay_reason: str | None = Query(None, alias="delayReason"),
    delayed: bool | None = None,
    driver_nc: bool | None = Query(None, alias="driverNc"),
    cab_nc: bool | None = Query(None, alias="cabNc"),
    sort: str = "scheduledArrival",
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    session: Session = Depends(get_db),
) -> DataDashboardResponse:
    return DataDashboardResponse.model_validate(get_trip_dashboard(
        session,
        settings,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        vendor=vendor,
        office=office,
        shift=shift,
        status=trip_status,
        delay_reason=delay_reason,
        delayed=delayed,
        driver_nc=driver_nc,
        cab_nc=cab_nc,
        sort=sort,
        direction=direction,
    ))


@app.get("/api/dashboards/feedback", response_model=DataDashboardResponse)
def get_feedback_data_dashboard(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=10, le=100),
    start_date: date | None = Query(None, alias="startDate"),
    end_date: date | None = Query(None, alias="endDate"),
    vendor: str | None = None,
    office: str | None = None,
    trip_type: str | None = Query(None, alias="tripType"),
    rating_category: str = Query("driver", alias="ratingCategory", pattern="^(route|driver|cab|safety|marshal)$"),
    max_rating: int | None = Query(None, alias="maxRating", ge=1, le=5),
    sort: str = "tripAt",
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    session: Session = Depends(get_db),
) -> DataDashboardResponse:
    return DataDashboardResponse.model_validate(get_feedback_dashboard(
        session,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        vendor=vendor,
        office=office,
        trip_type=trip_type,
        rating_category=rating_category,
        max_rating=max_rating,
        sort=sort,
        direction=direction,
    ))


@app.get("/api/dashboards/safety-alerts", response_model=DataDashboardResponse)
def get_safety_alerts_data_dashboard(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=10, le=100),
    start_date: date | None = Query(None, alias="startDate"),
    end_date: date | None = Query(None, alias="endDate"),
    state: str | None = None,
    severity: str | None = None,
    event_type: str | None = Query(None, alias="eventType"),
    vendor: str | None = None,
    office: str | None = None,
    employee: str | None = None,
    source: str | None = None,
    sort: str = "startedAt",
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    session: Session = Depends(get_db),
) -> DataDashboardResponse:
    return DataDashboardResponse.model_validate(get_alert_dashboard(
        session,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        state=state,
        severity=severity,
        event_type=event_type,
        vendor=vendor,
        office=office,
        employee=employee,
        source=source,
        sort=sort,
        direction=direction,
    ))


@app.get("/api/dashboards/{dashboard_name}/export")
def export_data_dashboard(
    dashboard_name: str,
    start_date: date | None = Query(None, alias="startDate"),
    end_date: date | None = Query(None, alias="endDate"),
    vendor: str | None = None,
    office: str | None = None,
    shift: str | None = None,
    trip_status: str | None = Query(None, alias="status"),
    delay_reason: str | None = Query(None, alias="delayReason"),
    delayed: bool | None = None,
    driver_nc: bool | None = Query(None, alias="driverNc"),
    cab_nc: bool | None = Query(None, alias="cabNc"),
    trip_type: str | None = Query(None, alias="tripType"),
    rating_category: str = Query("driver", alias="ratingCategory"),
    max_rating: int | None = Query(None, alias="maxRating", ge=1, le=5),
    state: str | None = None,
    severity: str | None = None,
    event_type: str | None = Query(None, alias="eventType"),
    employee: str | None = None,
    source: str | None = None,
    sort: str | None = None,
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    session: Session = Depends(get_db),
) -> StreamingResponse:
    common = {"page": 1, "page_size": 100_000, "start_date": start_date, "end_date": end_date}
    if dashboard_name == "trips":
        data = get_trip_dashboard(
            session,
            settings,
            **common,
            vendor=vendor,
            office=office,
            shift=shift,
            status=trip_status,
            delay_reason=delay_reason,
            delayed=delayed,
            driver_nc=driver_nc,
            cab_nc=cab_nc,
            sort=sort or "scheduledArrival",
            direction=direction,
        )
        columns = [
            ("tripId", "Trip ID"), ("scheduledArrival", "Scheduled arrival"),
            ("actualArrival", "Actual arrival"), ("vendorId", "Vendor"),
            ("officeId", "Office"), ("shiftId", "Shift"), ("status", "Status"),
            ("employeeCount", "Employees"), ("delayMinutes", "Delay minutes"),
            ("delayReason", "Delay reason"), ("noShowCount", "No-shows"),
            ("driverNonCompliance", "Driver NC"), ("cabNonCompliance", "Cab NC"),
        ]
    elif dashboard_name == "feedback":
        data = get_feedback_dashboard(
            session,
            **common,
            vendor=vendor,
            office=office,
            trip_type=trip_type,
            rating_category=rating_category,
            max_rating=max_rating,
            sort=sort or "tripAt",
            direction=direction,
        )
        columns = [
            ("tripId", "Trip ID"), ("tripAt", "Trip date"), ("employeeId", "Employee"),
            ("vendorId", "Vendor"), ("officeId", "Office"), ("tripType", "Trip type"),
            ("routeRating", "Route rating"), ("driverRating", "Driver rating"),
            ("cabRating", "Cab rating"), ("safetyRating", "Safety rating"),
            ("marshalRating", "Marshal rating"),
        ]
    elif dashboard_name == "safety-alerts":
        data = get_alert_dashboard(
            session,
            **common,
            state=state,
            severity=severity,
            event_type=event_type,
            vendor=vendor,
            office=office,
            employee=employee,
            source=source,
            sort=sort or "startedAt",
            direction=direction,
        )
        columns = [
            ("eventId", "Event ID"), ("tripId", "Trip ID"), ("startedAt", "Started at"),
            ("eventType", "Event type"), ("severity", "Severity"), ("state", "State"),
            ("employeeId", "Employee"), ("vendorId", "Vendor"), ("officeId", "Office"),
            ("source", "Source"), ("acknowledgedAt", "Acknowledged at"),
            ("responseMinutes", "Response minutes"),
        ]
    else:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    return StreamingResponse(
        csv_stream(columns, data["rows"]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{dashboard_name}-filtered.csv"'},
    )


@app.get("/api/operations", response_model=OperationsResponse)
def get_operations(session: Session = Depends(get_db)) -> OperationsResponse:
    return build_operations_response(session, settings)


@app.get("/api/operations/analytics", response_model=OperationsAnalyticsResponse)
def get_operations_analytics_endpoint(
    start_date: date | None = Query(None, alias="startDate"),
    end_date: date | None = Query(None, alias="endDate"),
    session: Session = Depends(get_db),
) -> OperationsAnalyticsResponse:
    try:
        return OperationsAnalyticsResponse.model_validate(
            get_operations_analytics(session, settings, start_date, end_date)
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/incidents/{incident_id}/related-trips", response_model=IncidentTripEvidenceResponse)
def get_incident_related_trips(
    incident_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=10, le=100),
    session: Session = Depends(get_db),
) -> IncidentTripEvidenceResponse:
    evidence = get_incident_trip_evidence(session, settings, incident_id, page, page_size)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentTripEvidenceResponse.model_validate(evidence)


@app.get("/api/agent/status")
def get_agent_status() -> dict[str, str | None]:
    return {
        "mode": "model" if settings.ai_api_key else "grounded-local",
        "model": settings.ai_model if settings.ai_api_key else None,
    }


@app.get("/api/tools/trips/summary")
def get_trip_summary_tool(
    startDate: date,
    endDate: date,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return get_trip_summary(session, settings, startDate, endDate)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/tools/trips/zero-delay-dates")
def get_zero_delay_dates_tool(
    startDate: date | None = None,
    endDate: date | None = None,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return get_zero_delay_dates(session, settings, startDate, endDate)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/tools/trips/highest-delay-days")
def get_highest_delay_days_tool(
    startDate: date | None = None,
    endDate: date | None = None,
    sortBy: str = "delayed_trips",
    limit: int = 5,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return get_highest_delay_days(session, settings, startDate, endDate, sortBy, limit)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _dimension_performance_tool(
    dimension: str,
    start_date: date | None,
    end_date: date | None,
    limit: int,
    session: Session,
) -> dict[str, object]:
    try:
        return get_dimension_performance(
            session,
            settings,
            dimension,
            start_date,
            end_date,
            limit,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/tools/vendors/performance")
def get_vendor_performance_tool(
    startDate: date | None = None,
    endDate: date | None = None,
    limit: int = 10,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    return _dimension_performance_tool("vendor", startDate, endDate, limit, session)


@app.get("/api/tools/routes/performance")
def get_route_performance_tool(
    startDate: date | None = None,
    endDate: date | None = None,
    limit: int = 10,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    return _dimension_performance_tool("route", startDate, endDate, limit, session)


@app.get("/api/tools/shifts/performance")
def get_shift_performance_tool(
    startDate: date | None = None,
    endDate: date | None = None,
    limit: int = 10,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    return _dimension_performance_tool("shift", startDate, endDate, limit, session)


@app.post("/api/tools/{tool_name}")
def execute_tool(
    tool_name: str,
    arguments: dict[str, object],
    session: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return execute_agent_tool(session, settings, tool_name, json.dumps(arguments))
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/agent/chat")
def chat_with_mobility_agent(
    request: MobilityAgentRequest,
    session: Session = Depends(get_db),
) -> StreamingResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    request.message = message
    try:
        context = build_agent_context(session, settings, request.incidentId)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return StreamingResponse(
        stream_agent_response(request, context, settings, session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/incidents", response_model=list[IncidentResponse])
def list_incidents(session: Session = Depends(get_db)) -> list[Incident]:
    return list(
        session.scalars(
            select(Incident).order_by(
                desc(Incident.attention_required),
                desc(Incident.updated_at),
            )
        )
    )


@app.get("/api/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, session: Session = Depends(get_db)) -> Incident:
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.get("/api/incidents/{incident_id}/events", response_model=list[IncidentEventResponse])
def get_incident_events(
    incident_id: int,
    session: Session = Depends(get_db),
) -> list[IncidentEvent]:
    if session.get(Incident, incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return list(
        session.scalars(
            select(IncidentEvent)
            .where(IncidentEvent.incident_id == incident_id)
            .order_by(IncidentEvent.created_at)
        )
    )


def _incident_email_draft(incident: Incident) -> IncidentEmailDraftResponse:
    recipient = f"{incident.contributing_vendor} operations team" if incident.contributing_vendor else "Mobility operations team"
    subject = f"Action required: {incident.title}"
    body = "\n".join(
        [
            "Hello team,",
            "",
            f"We are following up on the acknowledged mobility incident: {incident.title}.",
            f"Current performance is {incident.current_value}% against the {incident.sla_value}% SLA.",
            f"Employees affected: {incident.affected_employees}.",
            "",
            f"Evidence summary: {incident.reason}",
            "",
            f"Requested action: {incident.recommended_action}",
            "",
            "Please confirm ownership and share the recovery plan and expected completion time.",
            "",
            "Regards,",
            "SHLOK Mobility Operations",
        ]
    )
    return IncidentEmailDraftResponse(
        recipient=recipient,
        subject=subject,
        body=body,
        filename=f"incident-{incident.id}-email-draft.txt",
    )


@app.get("/api/incidents/{incident_id}/email-draft", response_model=IncidentEmailDraftResponse)
def get_incident_email_draft(
    incident_id: int,
    session: Session = Depends(get_db),
) -> IncidentEmailDraftResponse:
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status != "acknowledged":
        raise HTTPException(status_code=409, detail="Acknowledge the incident before drafting an email")
    return _incident_email_draft(incident)


@app.post("/api/incidents/{incident_id}/email-sent", response_model=IncidentEventResponse)
def mark_incident_email_sent(
    incident_id: int,
    session: Session = Depends(get_db),
) -> IncidentEvent:
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status != "acknowledged":
        raise HTTPException(status_code=409, detail="Acknowledge the incident before sending an email")
    existing = session.scalar(
        select(IncidentEvent)
        .where(IncidentEvent.incident_id == incident_id, IncidentEvent.event_type == "email_sent")
        .order_by(desc(IncidentEvent.created_at))
        .limit(1)
    )
    if existing is not None:
        return existing
    event = IncidentEvent(
        incident_id=incident.id,
        event_type="email_sent",
        metric_value=incident.current_value,
        message="Incident notification email was marked as sent by the transport manager.",
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@app.post("/api/incidents/{incident_id}/acknowledge", response_model=IncidentResponse)
def acknowledge_incident(incident_id: int, session: Session = Depends(get_db)) -> Incident:
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status in {"open", "reopened"}:
        incident.status = "acknowledged"
        incident.acknowledged_at = datetime.utcnow()
        incident.acknowledged_value = incident.current_value
        incident.attention_required = False
        incident.updated_at = datetime.utcnow()
        session.add(
            IncidentEvent(
                incident_id=incident.id,
                event_type="acknowledged",
                metric_value=incident.current_value,
                message=f"Manager acknowledged the incident at {incident.current_value}%.",
            )
        )
        session.commit()
        session.refresh(incident)
    return incident
