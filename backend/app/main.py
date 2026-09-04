from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.connection import SessionLocal, engine, get_db
from app.database.migrations import migrate_database
from app.database.models import DatasetUpload, Incident, IncidentEvent, MetricSnapshot
from app.schemas.api import DashboardResponse, IncidentEventResponse, IncidentResponse, UploadResponse
from app.services.ingestion import ingest_csv
from app.services.detection import evaluate_operations


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate_database(engine)
    with SessionLocal() as session:
        latest_dataset_id = session.scalar(
            select(DatasetUpload.id).order_by(desc(DatasetUpload.id)).limit(1)
        )
        if latest_dataset_id is not None:
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
async def upload_dataset(
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    try:
        upload, incident_created = ingest_csv(
            session,
            file.filename,
            await file.read(),
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
