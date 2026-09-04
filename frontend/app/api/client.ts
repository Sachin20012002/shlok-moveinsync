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

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getWorkspace(): Promise<[Dashboard, Incident[]]> {
  return Promise.all([request<Dashboard>("/api/dashboard"), request<Incident[]>("/api/incidents")]);
}

export async function uploadDataset(file: File): Promise<UploadResult> {
  const body = new FormData();
  body.append("file", file);
  return request<UploadResult>("/api/datasets/upload", { method: "POST", body });
}

export async function acknowledgeIncident(id: number): Promise<Incident> {
  return request<Incident>(`/api/incidents/${id}/acknowledge`, { method: "POST" });
}