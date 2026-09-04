from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OnTimeArrivalResponse(BaseModel):
    value: float | None
    sla: float
    previous_value: float | None = Field(alias="previousValue")
    status: str

    model_config = ConfigDict(populate_by_name=True)


class DashboardResponse(BaseModel):
    on_time_arrival: OnTimeArrivalResponse = Field(alias="onTimeArrival")
    completed_trips: int = Field(alias="completedTrips")
    delayed_trips: int = Field(alias="delayedTrips")
    affected_employees: int = Field(alias="affectedEmployees")
    average_delay_minutes: float | None = Field(alias="averageDelayMinutes")
    active_incident_count: int = Field(alias="activeIncidentCount")

    model_config = ConfigDict(populate_by_name=True)


class IncidentResponse(BaseModel):
    id: int
    title: str
    severity: str
    status: str
    current_value: float = Field(alias="currentValue")
    sla_value: float = Field(alias="slaValue")
    previous_value: float | None = Field(alias="previousValue")
    affected_employees: int = Field(alias="affectedEmployees")
    contributing_vendor: str | None = Field(alias="contributingVendor")
    contributing_route: str | None = Field(alias="contributingRoute")
    contributing_shift: str | None = Field(alias="contributingShift")
    reason: str
    recommended_action: str = Field(alias="recommendedAction")
    data_quality_warning: str | None = Field(alias="dataQualityWarning")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime | None = Field(alias="updatedAt")
    acknowledged_at: datetime | None = Field(alias="acknowledgedAt")
    acknowledged_value: float | None = Field(alias="acknowledgedValue")
    last_notified_at: datetime | None = Field(alias="lastNotifiedAt")
    last_notified_value: float | None = Field(alias="lastNotifiedValue")
    notification_count: int = Field(alias="notificationCount")
    attention_required: bool = Field(alias="attentionRequired")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UploadResponse(BaseModel):
    dataset_id: int = Field(alias="datasetId")
    filename: str
    valid_rows: int = Field(alias="validRows")
    invalid_rows: int = Field(alias="invalidRows")
    skipped_rows: int = Field(alias="skippedRows")
    incident_created: bool = Field(alias="incidentCreated")

    model_config = ConfigDict(populate_by_name=True)


class IncidentEventResponse(BaseModel):
    id: int
    event_type: str = Field(alias="eventType")
    metric_value: float = Field(alias="metricValue")
    message: str
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)