from datetime import datetime
from typing import Any
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


class PaginationResponse(BaseModel):
    page: int
    page_size: int = Field(alias="pageSize")
    total_rows: int = Field(alias="totalRows")
    total_pages: int = Field(alias="totalPages")

    model_config = ConfigDict(populate_by_name=True)


class DataDashboardResponse(BaseModel):
    summary: dict[str, int | float | None]
    facets: dict[str, list[str]]
    rows: list[dict[str, Any]]
    pagination: PaginationResponse

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


class IncidentEmailDraftResponse(BaseModel):
    recipient: str
    subject: str
    body: str
    filename: str

    model_config = ConfigDict(populate_by_name=True)


class TripExceptionResponse(BaseModel):
    trip_id: str = Field(alias="tripId")
    issue: str
    delay_minutes: float | None = Field(alias="delayMinutes")
    related_incident_ids: list[int] = Field(alias="relatedIncidentIds")
    vendor_id: str = Field(alias="vendorId")
    route_id: str = Field(alias="routeId")
    employee_id: str = Field(alias="employeeId")
    employee_count: int = Field(alias="employeeCount")
    recommended_action: str = Field(alias="recommendedAction")

    model_config = ConfigDict(populate_by_name=True)


class IncidentTripCountResponse(BaseModel):
    incident_id: int = Field(alias="incidentId")
    count: int

    model_config = ConfigDict(populate_by_name=True)


class ShiftReadinessResponse(BaseModel):
    shift_id: str = Field(alias="shiftId")
    completed_trips: int = Field(alias="completedTrips")
    delayed_trips: int = Field(alias="delayedTrips")
    missing_arrivals: int = Field(alias="missingArrivals")
    affected_employees: int = Field(alias="affectedEmployees")
    status: str

    model_config = ConfigDict(populate_by_name=True)


class VendorWatchResponse(BaseModel):
    vendor_id: str = Field(alias="vendorId")
    ota: float
    delayed_trips: int = Field(alias="delayedTrips")
    missing_gps: int = Field(alias="missingGps")
    attention_incidents: int = Field(alias="attentionIncidents")

    model_config = ConfigDict(populate_by_name=True)


class TimelineEventResponse(BaseModel):
    incident_id: int = Field(alias="incidentId")
    title: str
    event_type: str = Field(alias="eventType")
    message: str
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class DataQualityResponse(BaseModel):
    source_file: str | None = Field(alias="sourceFile")
    imported_rows: int = Field(alias="importedRows")
    missing_gps: int = Field(alias="missingGps")
    missing_arrivals: int = Field(alias="missingArrivals")
    invalid_rows: int = Field(alias="invalidRows")
    skipped_rows: int = Field(alias="skippedRows")
    last_data_update: datetime | None = Field(alias="lastDataUpdate")

    model_config = ConfigDict(populate_by_name=True)


class RecommendedActionResponse(BaseModel):
    incident_id: int = Field(alias="incidentId")
    severity: str
    title: str
    action: str

    model_config = ConfigDict(populate_by_name=True)


class OperationsResponse(BaseModel):
    active_trips: int = Field(alias="activeTrips")
    maximum_delay_minutes: float | None = Field(alias="maximumDelayMinutes")
    total_trip_exceptions: int = Field(alias="totalTripExceptions")
    trip_exceptions: list[TripExceptionResponse] = Field(alias="tripExceptions")
    incident_trip_counts: list[IncidentTripCountResponse] = Field(alias="incidentTripCounts")
    shift_readiness: list[ShiftReadinessResponse] = Field(alias="shiftReadiness")
    vendor_watchlist: list[VendorWatchResponse] = Field(alias="vendorWatchlist")
    timeline: list[TimelineEventResponse]
    data_quality: DataQualityResponse = Field(alias="dataQuality")
    recommended_actions: list[RecommendedActionResponse] = Field(alias="recommendedActions")

    model_config = ConfigDict(populate_by_name=True)


class DateRangeResponse(BaseModel):
    start_date: str | None = Field(alias="startDate")
    end_date: str | None = Field(alias="endDate")

    model_config = ConfigDict(populate_by_name=True)


class PerformanceSummaryResponse(BaseModel):
    completed_trips: int = Field(alias="completedTrips")
    delayed_trips: int = Field(alias="delayedTrips")
    ota: float | None
    affected_employees: int = Field(alias="affectedEmployees")
    average_delay_minutes: float = Field(alias="averageDelayMinutes")

    model_config = ConfigDict(populate_by_name=True)


class OperationsAnalyticsResponse(BaseModel):
    available_range: DateRangeResponse = Field(alias="availableRange")
    selected_range: DateRangeResponse = Field(alias="selectedRange")
    summary: PerformanceSummaryResponse
    vendor_performance: list[dict[str, Any]] = Field(alias="vendorPerformance")
    shift_performance: list[dict[str, Any]] = Field(alias="shiftPerformance")
    weekly_trend: list[dict[str, Any]] = Field(alias="weeklyTrend")

    model_config = ConfigDict(populate_by_name=True)


class IncidentTripEvidenceResponse(BaseModel):
    total_trips: int = Field(alias="totalTrips")
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")
    trips: list[dict[str, Any]]

    model_config = ConfigDict(populate_by_name=True)


class AgentMessage(BaseModel):
    role: str
    content: str


class MobilityAgentRequest(BaseModel):
    message: str
    history: list[AgentMessage] = Field(default_factory=list)
    incidentId: int | None = None