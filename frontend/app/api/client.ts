import type { Dashboard, Incident, IncidentEvent, Operations, UploadResult } from "@/types/api";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, options);
  } catch {
    throw new Error("The mobility service is unavailable. Confirm the backend is running and try again.");
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `The request failed with status ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export function getDashboard() { return request<Dashboard>("/api/dashboard"); }
export function getIncidents() { return request<Incident[]>("/api/incidents"); }
export function getOperations() { return request<Operations>("/api/operations"); }
export function getWorkspace(): Promise<[Dashboard, Incident[], Operations]> {
  return Promise.all([getDashboard(), getIncidents(), getOperations()]);
}
export function getIncident(id: number) { return request<Incident>(`/api/incidents/${id}`); }
export function getIncidentEvents(id: number) { return request<IncidentEvent[]>(`/api/incidents/${id}/events`); }
export function acknowledgeIncident(id: number) { return request<Incident>(`/api/incidents/${id}/acknowledge`, { method: "POST" }); }

export function uploadDataset(file: File) {
  const body = new FormData();
  body.append("file", file);
  return request<UploadResult>("/api/datasets/upload", { method: "POST", body });
}
