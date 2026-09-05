"use client";

import { Activity, AlertTriangle, ArrowUpRight, Bot, Building2, Check, ChevronRight, Clock3, Database, Gauge, LoaderCircle, MapPin, RefreshCw, Route, ShieldAlert, Users } from "lucide-react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { acknowledgeIncident, Dashboard, EMPTY_OPERATIONS, getWorkspace, Incident, Operations } from "./api/client";
import { MobileNav } from "./components/mobile-nav";
import styles from "./page.module.css";

const EMPTY_DASHBOARD: Dashboard = {
  onTimeArrival: { value: null, sla: 90, previousValue: null, status: "insufficient_data" },
  completedTrips: 0, delayedTrips: 0, affectedEmployees: 0, averageDelayMinutes: null, activeIncidentCount: 0,
};

function displayValue(value: number | null, suffix = "") {
  return value === null ? "Insufficient data" : `${value}${suffix}`;
}

export default function Home() {
  const [dashboard, setDashboard] = useState<Dashboard>(EMPTY_DASHBOARD);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [operations, setOperations] = useState<Operations>(EMPTY_OPERATIONS);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const priorityIncidents = incidents.filter((incident) => incident.attentionRequired).slice(0, 5);
  const selectedIncident = priorityIncidents.find((incident) => incident.id === selectedId) ?? priorityIncidents[0];
  const visibleTripExceptions = selectedIncident
    ? operations.tripExceptions.filter((trip) => trip.relatedIncidentIds.includes(selectedIncident.id))
    : operations.tripExceptions;
  const relatedTripTotal = selectedIncident
    ? operations.incidentTripCounts.find((item) => item.incidentId === selectedIncident.id)?.count ?? 0
    : operations.totalTripExceptions;

  async function refresh() {
    setError(null);
    try {
      const [nextDashboard, nextIncidents, nextOperations] = await getWorkspace();
      setDashboard(nextDashboard);
      setIncidents(nextIncidents);
      setOperations(nextOperations);
      const nextPriority = nextIncidents.filter((incident) => incident.attentionRequired);
      setSelectedId((current) => nextPriority.some((item) => item.id === current) ? current : (nextPriority[0]?.id ?? null));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to reach the backend");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleAcknowledge() {
    if (!selectedIncident) return;
    setError(null);
    try {
      await acknowledgeIncident(selectedIncident.id);
      await refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to acknowledge incident");
    }
  }

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}><span>SL</span><strong>SHLOK</strong></div>
        <nav aria-label="Primary navigation">
          <Link className={styles.navActive} href="/" aria-current="page"><Gauge size={18} /> Operations</Link>
          <Link href="/incidents"><ShieldAlert size={18} /> Incidents</Link>
          <Link href="/agent"><Bot size={18} /> Mobility Agent</Link>
          <button disabled title="Vendor workspace coming soon"><Building2 size={18} /> Vendors</button>
          <button disabled title="Route workspace coming soon"><Route size={18} /> Routes</button>
        </nav>
      </aside>

      <main className={styles.main}>
        <header className={styles.header}>
          <div><p className={styles.eyebrow}>LIVE OPERATIONS</p><h1>Mobility control room</h1><p>Service health, SLA exceptions, and actions that need an owner.</p></div>
          <div className={styles.headerActions}>
            <button className={styles.iconButton} onClick={() => void refresh()} title="Refresh data" aria-label="Refresh data" disabled={loading}>{loading ? <LoaderCircle className={styles.spin} size={18} /> : <RefreshCw size={18} />}</button>
            <div className={styles.profile}><span className={styles.profileAvatar}>TM</span><div><strong>Transport Manager</strong><small>Workspace profile</small></div></div>
          </div>
        </header>

        {error && <div className={styles.error} role="alert"><AlertTriangle size={18} /><span>{error}. Confirm FastAPI is running on port 8000.</span></div>}

        <section className={`${styles.metricBand} ${loading ? styles.metricsLoading : ""}`} aria-label="Operational metrics" aria-busy={loading}>
          {loading ? Array.from({ length: 4 }, (_, index) => <article className={styles.metricSkeleton} key={index}><span /><strong /><p /></article>) : <>
            <article className={styles.otaMetric}><div className={styles.metricLabel}><Activity size={18} /> On-time arrival</div><div className={styles.otaRow}><strong>{displayValue(dashboard.onTimeArrival.value, "%")}</strong><span className={dashboard.onTimeArrival.status === "healthy" ? styles.healthy : styles.breach}>SLA {dashboard.onTimeArrival.sla}%</span></div><p>{dashboard.onTimeArrival.previousValue === null ? "Historical comparison unavailable" : `Previous period ${dashboard.onTimeArrival.previousValue}%`}</p></article>
            <article><div className={styles.metricLabel}><Route size={18} /> Completed trips</div><strong>{dashboard.completedTrips}</strong><p>Eligible for OTA</p></article>
            <article><div className={styles.metricLabel}><Clock3 size={18} /> Delayed trips</div><strong>{dashboard.delayedTrips}</strong><p>Over 5 minutes late</p></article>
            <article><div className={styles.metricLabel}><Users size={18} /> Employees affected</div><strong>{dashboard.affectedEmployees}</strong><p>{displayValue(dashboard.averageDelayMinutes, " min avg delay")}</p></article>
          </>}
        </section>

        <section className={`${styles.workspace} ${styles.priorityWorkspace}`}>
          <div className={styles.incidentPane}>
            <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>PRIORITY QUEUE</p><h2>Incidents</h2></div><span>{dashboard.activeIncidentCount} need attention</span></div>
            {loading ? <div className={styles.empty}><LoaderCircle className={styles.spin} size={24} /><strong>Loading live signals</strong><p>Reading the latest operational state.</p></div> : priorityIncidents.length === 0 ? <div className={styles.empty}><Check size={24} /><strong>No active signals</strong><p>Nothing currently requires acknowledgment.</p></div> : (
              <div className={styles.incidentList}>{priorityIncidents.map((incident) => <button key={incident.id} className={selectedIncident?.id === incident.id ? styles.incidentSelected : styles.incidentItem} onClick={() => setSelectedId(incident.id)}><span className={`${styles.severity} ${styles[incident.severity]}`}>{incident.severity}</span><strong>{incident.title}</strong><small>{incident.currentValue}% against {incident.slaValue}% SLA{incident.status === "reopened" ? " · Re-acknowledgment required" : ""}</small><span className={styles.unread} title="Manager attention required" aria-label="Manager attention required" /><ChevronRight size={18} /></button>)}</div>
            )}
            <Link className={styles.viewAll} href="/incidents">View all incidents <ArrowUpRight size={15} /></Link>
          </div>

        </section>

        <section className={styles.operationsSection}>
          <div className={styles.sectionTitle}><div><p className={styles.eyebrow}>INCIDENT EVIDENCE</p><h2>{selectedIncident ? "Trips related to this incident" : "All trip exceptions"}</h2><p className={styles.scopeNote}>{selectedIncident ? `Showing up to ${visibleTripExceptions.length} trips that contribute to “${selectedIncident.title}”.` : "No priority incident is selected, so a sample of current exceptions is shown."}</p></div><span>{relatedTripTotal} {relatedTripTotal === 1 ? "trip" : "trips"}</span></div>
          <div className={styles.tableWrap}>
            <table><thead><tr><th>Trip</th><th>Issue</th><th>Vendor</th><th>Route</th><th>Employees</th><th>Next action</th></tr></thead><tbody>
              {visibleTripExceptions.length === 0 ? <tr><td colSpan={6} className={styles.tableEmpty}>No trips are directly related to this incident.</td></tr> : visibleTripExceptions.map((trip) => <tr key={trip.tripId}><td><strong>{trip.tripId}</strong></td><td><span className={styles.issue}>{trip.issue}</span></td><td>{trip.vendorId}</td><td>{trip.routeId}</td><td>{trip.employeeCount}</td><td>{trip.recommendedAction}</td></tr>)}
            </tbody></table>
          </div>
        </section>

        <section className={styles.splitSection}>
          <div className={styles.dataPanel}><div className={styles.sectionTitle}><div><p className={styles.eyebrow}>READINESS</p><h2>Shift status</h2></div><Users size={20} /></div><div className={styles.compactList}>
            {operations.shiftReadiness.map((shift) => <div key={shift.shiftId} className={styles.compactRow}><div><strong>{shift.shiftId}</strong><span>{shift.completedTrips} complete · {shift.delayedTrips} delayed · {shift.affectedEmployees} affected</span></div><span className={`${styles.readiness} ${styles[shift.status]}`}>{shift.status.replace("_", " ")}</span></div>)}
          </div></div>
          <div className={styles.dataPanel}><div className={styles.sectionTitle}><div><p className={styles.eyebrow}>WATCHLIST</p><h2>Vendor performance</h2></div><Building2 size={20} /></div><div className={styles.compactList}>
            {operations.vendorWatchlist.map((vendor) => <div key={vendor.vendorId} className={styles.vendorRow}><div><strong>{vendor.vendorId}</strong><span>{vendor.delayedTrips} delayed · {vendor.missingGps} GPS gaps</span></div><strong>{vendor.ota}% OTA</strong><span>{vendor.attentionIncidents} alerts</span></div>)}
          </div></div>
        </section>

        <section className={styles.splitSection}>
          <div className={styles.dataPanel}><div className={styles.sectionTitle}><div><p className={styles.eyebrow}>ACTIVITY</p><h2>Operational timeline</h2></div><Clock3 size={20} /></div><div className={styles.timeline}>
            {operations.timeline.length === 0 ? <p className={styles.panelEmpty}>No incident activity yet.</p> : operations.timeline.map((event, index) => <div key={`${event.incidentId}-${event.createdAt}-${index}`}><span className={styles.timelineDot} /><time dateTime={event.createdAt}>{new Date(event.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time><p><strong>{event.eventType}</strong> · {event.title}</p><small>{event.message}</small></div>)}
          </div></div>
          <div className={styles.dataPanel}><div className={styles.sectionTitle}><div><p className={styles.eyebrow}>INGESTION HEALTH</p><h2>Data quality</h2><p className={styles.scopeNote}>{operations.dataQuality.sourceFile ?? "No dataset loaded"} · {operations.dataQuality.importedRows.toLocaleString()} rows</p></div><Database size={20} /></div><div className={styles.qualityGrid}><div><span>Missing GPS</span><strong>{operations.dataQuality.missingGps}</strong></div><div><span>Missing arrivals</span><strong>{operations.dataQuality.missingArrivals}</strong></div><div><span>Invalid rows</span><strong>{operations.dataQuality.invalidRows}</strong></div><div><span>Skipped rows</span><strong>{operations.dataQuality.skippedRows}</strong></div></div><p className={styles.lastUpdated}><MapPin size={14} /> Last data update {operations.dataQuality.lastDataUpdate ? new Date(operations.dataQuality.lastDataUpdate).toLocaleString() : "unavailable"}</p></div>
        </section>

        <section className={styles.operationsSection}>
          <div className={styles.sectionTitle}><div><p className={styles.eyebrow}>ACTION QUEUE</p><h2>Recommended next moves</h2></div><ArrowUpRight size={20} /></div>
          <div className={styles.actionList}>{operations.recommendedActions.length === 0 ? <p className={styles.panelEmpty}>No actions awaiting review.</p> : operations.recommendedActions.map((action) => <button key={action.incidentId} onClick={() => setSelectedId(action.incidentId)}><span className={`${styles.severity} ${styles[action.severity]}`}>{action.severity}</span><div><strong>{action.title}</strong><p>{action.action}</p></div><ChevronRight size={18} /></button>)}</div>
        </section>
      </main>
      <MobileNav active="operations" />
    </div>
  );
}
