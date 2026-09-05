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
  totalTripExceptions: number;
  tripExceptions: Array<{
    tripId: string;
    issue: string;
    delayMinutes: number | null;
    relatedIncidentIds: number[];
    vendorId: string;
    routeId: string;
    employeeId: string;
    employeeCount: number;
    recommendedAction: string;
  }>;
  incidentTripCounts: Array<{
    incidentId: number;
    count: number;
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
    sourceFile: string | null;
    importedRows: number;
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

export type PerformanceSummary = {
  completedTrips: number;
  delayedTrips: number;
  ota: number | null;
  affectedEmployees: number;
  averageDelayMinutes: number;
};

export type OperationsAnalytics = {
  availableRange: { startDate: string | null; endDate: string | null };
  selectedRange: { startDate: string | null; endDate: string | null };
  summary: PerformanceSummary;
  vendorPerformance: Array<PerformanceSummary & { vendorId: string }>;
  shiftPerformance: Array<PerformanceSummary & { shiftId: string }>;
  weeklyTrend: Array<PerformanceSummary & { weekStart: string; changePoints: number | null }>;
};

export type IncidentTripEvidence = {
  totalTrips: number;
  page: number;
  pageSize: number;
  totalPages: number;
  trips: Array<{
    tripId: string;
    scheduledArrival: string;
    vendorId: string;
    routeId: string;
    shiftId: string;
    employeeCount: number;
    delayMinutes: number;
    delayReason: string | null;
    issue: string;
  }>;
};

export type AgentMessage = {
  role: "user" | "assistant";
  content: string;
};

export type AgentContext = {
  mode: "model" | "grounded-local";
  model: string | null;
  scope: "general" | "incident";
  incidentId: number | null;
  incidentTitle: string | null;
  sourceFile: string | null;
  completedTrips: number;
  attentionIncidents: number;
};

export type DataDashboardKind = "trips" | "feedback" | "safety-alerts";

export type DataDashboard = {
  summary: Record<string, number | null>;
  facets: Record<string, string[]>;
  rows: Array<Record<string, string | number | boolean | null>>;
  pagination: {
    page: number;
    pageSize: number;
    totalRows: number;
    totalPages: number;
  };
};

export type DashboardQuery = Record<string, string | number | boolean | null | undefined>;

export const EMPTY_OPERATIONS: Operations = {
  activeTrips: 0,
  maximumDelayMinutes: null,
  totalTripExceptions: 0,
  tripExceptions: [],
  incidentTripCounts: [],
  shiftReadiness: [],
  vendorWatchlist: [],
  timeline: [],
  dataQuality: { sourceFile: null, importedRows: 0, missingGps: 0, missingArrivals: 0, invalidRows: 0, skippedRows: 0, lastDataUpdate: null },
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

export async function getDashboard(): Promise<Dashboard> {
  return request<Dashboard>("/api/dashboard");
}

export async function getOperations(): Promise<Operations> {
  return request<Operations>("/api/operations");
}

export async function getOperationsAnalytics(startDate?: string, endDate?: string): Promise<OperationsAnalytics> {
  const params = new URLSearchParams();
  if (startDate) params.set("startDate", startDate);
  if (endDate) params.set("endDate", endDate);
  return request<OperationsAnalytics>(`/api/operations/analytics?${params.toString()}`);
}

export async function getDataDashboard(kind: DataDashboardKind, query: DashboardQuery): Promise<DataDashboard> {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") params.set(key, String(value));
  });
  return request<DataDashboard>(`/api/dashboards/${kind}?${params.toString()}`);
}

export function getDataDashboardExportUrl(kind: DataDashboardKind, query: DashboardQuery): string {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (key !== "page" && key !== "pageSize" && value !== null && value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  return `${API_URL}/api/dashboards/${kind}/export?${params.toString()}`;
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

export async function getIncidentTrips(id: number, page = 1, pageSize = 25): Promise<IncidentTripEvidence> {
  return request<IncidentTripEvidence>(`/api/incidents/${id}/related-trips?page=${page}&pageSize=${pageSize}`);
}

export async function getAgentStatus(): Promise<Pick<AgentContext, "mode" | "model">> {
  return request<Pick<AgentContext, "mode" | "model">>("/api/agent/status");
}

export async function streamAgent(
  message: string,
  history: AgentMessage[],
  incidentId: number | null,
  handlers: {
    onContext: (context: AgentContext) => void;
    onToken: (content: string) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_URL}/api/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, incidentId }),
    signal,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Agent request failed with status ${response.status}`);
  }
  if (!response.body) throw new Error("Agent stream is unavailable");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const event = frame.match(/^event: (.+)$/m)?.[1];
      const data = frame.match(/^data: (.+)$/m)?.[1];
      if (!event || !data) continue;
      const payload = JSON.parse(data) as AgentContext & { content?: string; message?: string; ok?: boolean };
      if (event === "context") handlers.onContext(payload);
      if (event === "token" && payload.content) handlers.onToken(payload.content);
      if (event === "error") throw new Error(payload.message ?? "Agent stream failed");
    }
    if (done) break;
  }
}