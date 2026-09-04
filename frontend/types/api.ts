export type DashboardStatus = "healthy" | "critical" | "insufficient_data";
export type IncidentSeverity = "warning" | "high" | "critical";
export type IncidentStatus = "open" | "acknowledged" | "reopened" | "resolved";

export type Dashboard = {
  onTimeArrival: { value: number | null; sla: number; previousValue: number | null; status: DashboardStatus };
  completedTrips: number;
  delayedTrips: number;
  affectedEmployees: number;
  averageDelayMinutes: number | null;
  activeIncidentCount: number;
};

export type Incident = {
  id: number;
  title: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
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

export type IncidentEvent = { id: number; eventType: string; metricValue: number; message: string; createdAt: string };

export type UploadResult = {
  datasetId: number;
  filename: string;
  validRows: number;
  invalidRows: number;
  skippedRows: number;
  incidentCreated: boolean;
};

export type TripException = {
  tripId: string;
  issue: string;
  delayMinutes: number | null;
  relatedIncidentIds: number[];
  vendorId: string;
  routeId: string;
  employeeId: string;
  recommendedAction: string;
};

export type ShiftReadiness = {
  shiftId: string;
  completedTrips: number;
  delayedTrips: number;
  missingArrivals: number;
  affectedEmployees: number;
  status: "ready" | "at_risk" | "critical";
};

export type VendorWatch = {
  vendorId: string;
  ota: number;
  delayedTrips: number;
  missingGps: number;
  attentionIncidents: number;
};

export type Operations = {
  activeTrips: number;
  maximumDelayMinutes: number | null;
  tripExceptions: TripException[];
  shiftReadiness: ShiftReadiness[];
  vendorWatchlist: VendorWatch[];
  timeline: Array<{ incidentId: number; title: string; eventType: string; message: string; createdAt: string }>;
  dataQuality: { missingGps: number; missingArrivals: number; invalidRows: number; skippedRows: number; lastDataUpdate: string | null };
  recommendedActions: Array<{ incidentId: number; severity: IncidentSeverity; title: string; action: string }>;
};
