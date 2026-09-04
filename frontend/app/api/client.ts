export type Dashboard = {
  onTimeArrival: { value: number | null; sla: number; previousValue: number | null; status: "healthy" | "critical" | "insufficient_data" };
  completedTrips: number;
  delayedTrips: number;
  affectedEmployees: number;
  averageDelayMinutes: number | null;
  activeIncidentCount: number;
};

export type Incident = {
  id: number;
  title: string;
  severity: "warning" | "high" | "critical";
  status: "open" | "acknowledged" | "reopened" | "resolved";
  currentValue: number;
  slaValue: number;
  previousValue: number | null;
  affectedEmployees: number;
  contributingVendor: string | null;
  contributingRoute: string | null;
  contributingShift: string | null;
  reason: string;
  recommendedAction: string;
  dataQualityWarning: string | null;
  createdAt: string;
  updatedAt: string | null;
  acknowledgedAt: string | null;
  acknowledgedValue: number | null;
  lastNotifiedAt: string | null;
  lastNotifiedValue: number | null;
  notificationCount: number;
  attentionRequired: boolean;
};

export type UploadResult = {
  datasetId: number;
  filename: string;
  validRows: number;
  invalidRows: number;
  skippedRows: number;
  incidentCreated: boolean;
};

export type Operations = {
  activeTrips: number;
  maximumDelayMinutes: number | null;
  tripExceptions: Array<{
    tripId: string;
    issue: string;
    delayMinutes: number | null;
    relatedIncidentIds: number[];
    vendorId: string;
    routeId: string;
    employeeId: string;
    recommendedAction: string;
  }>;
  shiftReadiness: Array<{
    shiftId: string;
    completedTrips: number;
    delayedTrips: number;
    missingArrivals: number;
    affectedEmployees: number;
    status: "ready" | "at_risk" | "critical";
  }>;
  vendorWatchlist: Array<{
    vendorId: string;
    ota: number;
    delayedTrips: number;
    missingGps: number;
    attentionIncidents: number;
  }>;
  timeline: Array<{
    incidentId: number;
    title: string;
    eventType: string;
    message: string;
    createdAt: string;
  }>;
  dataQuality: {
    missingGps: number;
    missingArrivals: number;
    invalidRows: number;
    skippedRows: number;
    lastDataUpdate: string | null;
  };
  recommendedActions: Array<{
    incidentId: number;
    severity: "warning" | "high" | "critical";
    title: string;
    action: string;
  }>;
};

export type IncidentEvent = {
  id: number;
  eventType: string;
  metricValue: number;
  message: string;
  createdAt: string;
};

export const EMPTY_OPERATIONS: Operations = {
  activeTrips: 0,
  maximumDelayMinutes: null,
  tripExceptions: [],
  shiftReadiness: [],
  vendorWatchlist: [],
  timeline: [],
  dataQuality: { missingGps: 0, missingArrivals: 0, invalidRows: 0, skippedRows: 0, lastDataUpdate: null },
  recommendedActions: [],
};

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getWorkspace(): Promise<[Dashboard, Incident[], Operations]> {
  return Promise.all([
    request<Dashboard>("/api/dashboard"),
    request<Incident[]>("/api/incidents"),
    request<Operations>("/api/operations"),
  ]);
}

export async function uploadDataset(file: File): Promise<UploadResult> {
  const body = new FormData();
  body.append("file", file);
  return request<UploadResult>("/api/datasets/upload", { method: "POST", body });
}

export async function acknowledgeIncident(id: number): Promise<Incident> {
  return request<Incident>(`/api/incidents/${id}/acknowledge`, { method: "POST" });
}

export async function getIncidents(): Promise<Incident[]> {
  return request<Incident[]>("/api/incidents");
}

export async function getIncidentEvents(id: number): Promise<IncidentEvent[]> {
  return request<IncidentEvent[]>(`/api/incidents/${id}/events`);
}