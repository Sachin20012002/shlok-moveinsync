"use client";

import { Activity, AlertTriangle, Clock3, Route, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { getWorkspace } from "@/app/api/client";
import { DatasetUpload } from "@/components/DatasetUpload";
import { FeedbackState } from "@/components/FeedbackState";
import { MetricCard } from "@/components/MetricCard";
import { OperationalBrief } from "@/components/OperationalBrief";
import { OperationsPanels } from "@/components/OperationsPanels";
import type { Dashboard, Incident, Operations } from "@/types/api";
import styles from "./page.module.css";

const EMPTY_DASHBOARD: Dashboard = { onTimeArrival: { value: null, sla: 90, previousValue: null, status: "insufficient_data" }, completedTrips: 0, delayedTrips: 0, affectedEmployees: 0, averageDelayMinutes: null, activeIncidentCount: 0 };
const EMPTY_OPERATIONS: Operations = { activeTrips: 0, maximumDelayMinutes: null, tripExceptions: [], shiftReadiness: [], vendorWatchlist: [], timeline: [], dataQuality: { missingGps: 0, missingArrivals: 0, invalidRows: 0, skippedRows: 0, lastDataUpdate: null }, recommendedActions: [] };

function metric(value: number | null, suffix = "") { return value === null ? "—" : `${value}${suffix}`; }

export default function OperationsPage() {
  const [dashboard, setDashboard] = useState<Dashboard>(EMPTY_DASHBOARD);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [operations, setOperations] = useState<Operations>(EMPTY_OPERATIONS);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function applyWorkspace([nextDashboard, nextIncidents, nextOperations]: [Dashboard, Incident[], Operations]) {
    setDashboard(nextDashboard); setIncidents(nextIncidents); setOperations(nextOperations);
  }

  async function refreshWorkspace() {
    setRefreshing(true); setError(null);
    try { applyWorkspace(await getWorkspace()); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Unable to refresh operations data"); }
    finally { setLoading(false); setRefreshing(false); }
  }

  useEffect(() => { let active = true; getWorkspace().then((workspace) => { if (active) applyWorkspace(workspace); }).catch((requestError: unknown) => { if (active) setError(requestError instanceof Error ? requestError.message : "Unable to load operations data"); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);

  useEffect(() => {
    const elements = document.querySelectorAll<HTMLElement>("[data-reveal]");
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add(styles.revealVisible);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });

    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [loading]);

  const priorityIncident = incidents.find((incident) => incident.attentionRequired);

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div><p className={styles.eyebrow}>Mobility decision desk</p><h1>Operations</h1><p className={styles.intro}>A decision-first view of service risk, evidence, impact, and the next manager action.</p></div>
        <button className={styles.refreshButton} onClick={() => void refreshWorkspace()} disabled={refreshing}><Clock3 size={17} />{refreshing ? "Refreshing" : "Refresh data"}</button>
      </header>
      {error && <div className={styles.errorBanner} role="alert"><AlertTriangle size={19} /><div><strong>Operations data could not be loaded</strong><span>{error}</span></div><button onClick={() => void refreshWorkspace()}>Try again</button></div>}
      {loading ? <FeedbackState kind="loading" title="Building the operational brief" description="Evaluating metrics, incidents, and current trip evidence." /> : <>
        <div className={styles.revealItem} data-reveal><OperationalBrief dashboard={dashboard} operations={operations} incident={priorityIncident} /></div>
        <div className={styles.revealItem} data-reveal><section className={styles.metrics} aria-label="Operational pulse">
          <MetricCard label="On-time arrival" value={metric(dashboard.onTimeArrival.value, "%")} detail={dashboard.onTimeArrival.previousValue === null ? "No previous period" : `${dashboard.onTimeArrival.previousValue}% previous period`} reference={`SLA ${dashboard.onTimeArrival.sla}%`} tone={dashboard.onTimeArrival.status === "healthy" ? "healthy" : dashboard.onTimeArrival.status === "critical" ? "critical" : "neutral"} icon={<Activity size={19} />} featured />
          <MetricCard label="Active trips" value={String(operations.activeTrips)} detail={`${dashboard.completedTrips} completed`} icon={<Route size={19} />} />
          <MetricCard label="Maximum delay" value={metric(operations.maximumDelayMinutes, " min")} detail={`${dashboard.delayedTrips} delayed trips`} tone={dashboard.delayedTrips > 0 ? "warning" : "neutral"} icon={<Clock3 size={19} />} />
          <MetricCard label="Employees affected" value={String(dashboard.affectedEmployees)} detail={metric(dashboard.averageDelayMinutes, " min average delay")} icon={<Users size={19} />} />
        </section></div>
        <div className={styles.revealItem} data-reveal><OperationsPanels operations={operations} /></div>
        <div className={styles.revealItem} data-reveal><section className={styles.uploadSection}><DatasetUpload onUploaded={refreshWorkspace} /><div><p className={styles.eyebrow}>Deterministic flow</p><h2>Data becomes a decision trail</h2><p>Validated trip records update official metrics. Threshold rules detect incidents, and every acknowledgement is captured in the incident lifecycle.</p></div></section></div>
      </>}
    </div>
  );
}
