"use client";

import { Activity, ArrowLeft, ArrowUpDown, Bot, Check, ChevronLeft, ChevronRight, Clock3, Database, Download, Gauge, LoaderCircle, Mail, Route, Send, ShieldAlert, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { acknowledgeIncident, getIncidentEmailDraft, getIncidentEvents, getIncidents, getIncidentTrips, Incident, IncidentEmailDraft, IncidentEvent, IncidentTripEvidence, markIncidentEmailSent } from "../api/client";
import { BrandLockup } from "../components/brand-lockup";
import { MobileNav } from "../components/mobile-nav";
import styles from "./incidents.module.css";

const EMPTY_EVIDENCE: IncidentTripEvidence = { totalTrips: 0, page: 1, pageSize: 25, totalPages: 1, trips: [] };
type StatusFilter = "all" | Incident["status"];
type SortMode = "created" | "severity";
const SEVERITY_ORDER: Record<Incident["severity"], number> = { critical: 3, high: 2, warning: 1 };

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [events, setEvents] = useState<IncidentEvent[]>([]);
  const [evidence, setEvidence] = useState<IncidentTripEvidence>(EMPTY_EVIDENCE);
  const [evidencePage, setEvidencePage] = useState(1);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortMode, setSortMode] = useState<SortMode>("created");
  const [emailDraft, setEmailDraft] = useState<IncidentEmailDraft | null>(null);
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailSending, setEmailSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const filtered = incidents
    .filter((incident) => statusFilter === "all" || incident.status === statusFilter)
    .sort((left, right) => sortMode === "created"
      ? Date.parse(right.createdAt) - Date.parse(left.createdAt)
      : SEVERITY_ORDER[right.severity] - SEVERITY_ORDER[left.severity] || Date.parse(right.createdAt) - Date.parse(left.createdAt));
  const selected = filtered.find((incident) => incident.id === selectedId) ?? filtered[0];
  const emailSent = events.some((event) => event.eventType === "email_sent");

  async function loadIncidents() {
    try {
      const next = await getIncidents();
      setIncidents(next);
      const requestedId = Number(new URLSearchParams(window.location.search).get("incidentId"));
      setSelectedId((current) => next.some((item) => item.id === current) ? current : (next.some((item) => item.id === requestedId) ? requestedId : (next[0]?.id ?? null)));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load incidents");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadIncidents(); }, []);
  useEffect(() => {
    if (!selected) { setEvents([]); return; }
    void getIncidentEvents(selected.id).then(setEvents).catch(() => setEvents([]));
  }, [selected?.id]);
  useEffect(() => {
    if (!selected) { setEvidence(EMPTY_EVIDENCE); return; }
    let active = true;
    setEvidenceLoading(true);
    void getIncidentTrips(selected.id, evidencePage)
      .then((nextEvidence) => { if (active) setEvidence(nextEvidence); })
      .catch(() => { if (active) setEvidence(EMPTY_EVIDENCE); })
      .finally(() => { if (active) setEvidenceLoading(false); });
    return () => { active = false; };
  }, [selected?.id, evidencePage]);

  function selectIncident(id: number) {
    setSelectedId(id);
    setEvidencePage(1);
    setEmailDraft(null);
    window.history.replaceState(null, "", `/incidents?incidentId=${id}`);
  }

  async function acknowledge() {
    if (!selected) return;
    setError(null);
    try {
      await acknowledgeIncident(selected.id);
      await loadIncidents();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to acknowledge incident");
    }
  }

  async function openEmailDraft() {
    if (!selected) return;
    setEmailLoading(true);
    setError(null);
    try {
      setEmailDraft(await getIncidentEmailDraft(selected.id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to draft incident email");
    } finally {
      setEmailLoading(false);
    }
  }

  function downloadEmailDraft() {
    if (!emailDraft) return;
    const content = `To: ${emailDraft.recipient}\nSubject: ${emailDraft.subject}\n\n${emailDraft.body}\n`;
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = emailDraft.filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function sendEmail() {
    if (!selected || emailSent) return;
    setEmailSending(true);
    setError(null);
    try {
      const event = await markIncidentEmailSent(selected.id);
      setEvents((current) => current.some((item) => item.id === event.id) ? current : [...current, event]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to mark email as sent");
    } finally {
      setEmailSending(false);
    }
  }

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <BrandLockup />
        <nav aria-label="Primary navigation">
          <Link href="/"><Gauge size={18} /> Operations</Link>
          <Link className={styles.navActive} href="/incidents" aria-current="page"><ShieldAlert size={18} /> Incidents</Link>
          <Link href="/agent"><Bot size={18} /> Mobility Agent</Link>
          <Link href="/trips"><Database size={18} /> Data dashboards</Link>
        </nav>
        <div className={styles.persona}><span>Viewing as</span><strong>Transport Manager</strong></div>
      </aside>

      <main className={styles.page}>
        <header><Link className={styles.backLink} href="/"><ArrowLeft size={17} /> Operations</Link><p>INCIDENT WORKSPACE</p><h1>Incident lifecycle</h1><span>Review every signal, acknowledgment, escalation, and recovery.</span></header>
        {error && <div className={styles.error} role="alert">{error}</div>}
        <div className={styles.filterBar}>
          <div className={styles.filterGroup}><strong>Status</strong><div className={styles.filters}>{(["all", "open", "reopened", "acknowledged", "resolved"] as StatusFilter[]).map((value) => <button key={value} className={statusFilter === value ? styles.filterActive : ""} onClick={() => setStatusFilter(value)}>{value} <span>{value === "all" ? incidents.length : incidents.filter((item) => item.status === value).length}</span></button>)}</div></div>
          <button className={styles.sortButton} onClick={() => setSortMode((current) => current === "created" ? "severity" : "created")} title="Toggle incident sorting"><ArrowUpDown size={15} /> Sort: {sortMode === "created" ? "Creation time" : "Severity"}</button>
        </div>

        <section className={styles.workspace}>
          <div className={styles.list}>{loading ? <div className={styles.empty}><LoaderCircle className={styles.spin} size={24} /><strong>Loading incidents</strong><span>Retrieving the latest lifecycle state.</span></div> : filtered.length === 0 ? <div className={styles.empty}><ShieldAlert size={24} /><strong>No matching incidents</strong><span>Choose another status to continue reviewing.</span></div> : filtered.map((incident) => <button key={incident.id} className={selected?.id === incident.id ? styles.selected : ""} onClick={() => selectIncident(incident.id)}><span className={`${styles.severity} ${styles[incident.severity]}`}>{incident.severity}</span><strong>{incident.title}</strong><small>{incident.currentValue}% / {incident.slaValue}% SLA</small><em>{incident.status}</em></button>)}</div>
          <article className={styles.detail}>{!selected ? <div className={styles.empty}><Activity size={24} /><strong>{loading ? "Loading incident" : "No incident selected"}</strong><span>{loading ? "Lifecycle details will appear shortly." : "Select an incident or choose another filter."}</span></div> : <><div className={styles.detailHead}><div><span className={`${styles.severity} ${styles[selected.severity]}`}>{selected.severity}</span><h2>{selected.title}</h2></div><strong>{selected.status}</strong></div><div className={styles.values}><div><span>Current</span><strong>{selected.currentValue}%</strong></div><div><span>Acknowledged at</span><strong>{selected.acknowledgedValue === null ? "Not yet" : `${selected.acknowledgedValue}%`}</strong></div><div><span>Notifications</span><strong>{selected.notificationCount}</strong></div></div><p className={styles.reason}>{selected.reason}</p><div className={styles.action}><span>Recommended action</span><p>{selected.recommendedAction}</p></div><div className={styles.detailActions}>{selected.attentionRequired && <button className={styles.ack} onClick={() => void acknowledge()}><Check size={17} /> {selected.status === "reopened" ? "Re-acknowledge" : "Acknowledge"}</button>}{selected.status === "acknowledged" && <button className={emailSent ? styles.emailSentButton : styles.draftEmail} onClick={() => void openEmailDraft()} disabled={emailLoading}>{emailLoading ? <LoaderCircle className={styles.spin} size={17} /> : emailSent ? <Check size={17} /> : <Mail size={17} />} {emailSent ? "Email sent" : "Draft email"}</button>}<Link className={styles.askAgent} href={`/agent?incidentId=${selected.id}`}><Bot size={17} /> Ask Mobility Agent</Link></div><div className={styles.history}><h3><Clock3 size={17} /> Lifecycle history</h3>{events.length === 0 ? <p className={styles.historyEmpty}>No lifecycle events recorded.</p> : events.map((event) => <div key={event.id} data-event={event.eventType}><Activity size={14} /><time dateTime={event.createdAt}>{new Date(event.createdAt).toLocaleString()}</time><strong>{event.eventType.replaceAll("_", " ")}</strong><p>{event.message}</p></div>)}</div></>}</article>
        </section>

        {selected && <section className={styles.evidencePanel} aria-label="Trips related to selected incident">
          <div className={styles.evidenceHeader}><div><p>INCIDENT EVIDENCE</p><h2>Trips related to this incident</h2><span>{evidence.totalTrips.toLocaleString()} matching trips across {evidence.totalPages.toLocaleString()} {evidence.totalPages === 1 ? "page" : "pages"}</span></div><div className={styles.evidenceSummary}><Route size={18} /><strong>{evidence.totalTrips.toLocaleString()}</strong><span>related trips</span></div></div>
          <div className={styles.evidenceTable}><table><thead><tr><th>Trip</th><th>Scheduled date</th><th>Issue</th><th>Delay</th><th>Vendor</th><th>Route</th><th>Shift</th><th>Employees</th></tr></thead><tbody>{evidenceLoading ? <tr><td colSpan={8} className={styles.tableMessage}><LoaderCircle className={styles.spin} size={20} /> Loading related trips</td></tr> : evidence.trips.length === 0 ? <tr><td colSpan={8} className={styles.tableMessage}>No directly related trips found.</td></tr> : evidence.trips.map((trip) => <tr key={trip.tripId}><td><strong>{trip.tripId}</strong></td><td>{new Date(trip.scheduledArrival).toLocaleDateString()}</td><td>{trip.delayReason ?? trip.issue}</td><td><span className={styles.delayBadge}>{trip.delayMinutes} min</span></td><td>{trip.vendorId}</td><td>{trip.routeId}</td><td>{trip.shiftId}</td><td>{trip.employeeCount}</td></tr>)}</tbody></table></div>
          <div className={styles.pagination}><span>Page {evidence.page} of {evidence.totalPages}</span><div><button onClick={() => setEvidencePage((current) => Math.max(1, current - 1))} disabled={evidenceLoading || evidence.page <= 1}><ChevronLeft size={16} /> Previous</button><button onClick={() => setEvidencePage((current) => Math.min(evidence.totalPages, current + 1))} disabled={evidenceLoading || evidence.page >= evidence.totalPages}>Next <ChevronRight size={16} /></button></div></div>
        </section>}
        {emailDraft && <div className={styles.modalBackdrop} role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setEmailDraft(null); }}><section className={styles.emailModal} role="dialog" aria-modal="true" aria-labelledby="email-draft-title"><header><div><p>ACKNOWLEDGED INCIDENT</p><h2 id="email-draft-title">Incident email draft</h2></div><button onClick={() => setEmailDraft(null)} title="Close email draft" aria-label="Close email draft"><X size={19} /></button></header><div className={styles.emailFields}><label>To<input value={emailDraft.recipient} onChange={(event) => setEmailDraft({ ...emailDraft, recipient: event.target.value })} /></label><label>Subject<input value={emailDraft.subject} onChange={(event) => setEmailDraft({ ...emailDraft, subject: event.target.value })} /></label><label>Message<textarea rows={14} value={emailDraft.body} onChange={(event) => setEmailDraft({ ...emailDraft, body: event.target.value })} /></label></div><footer><button className={styles.downloadDraft} onClick={downloadEmailDraft}><Download size={17} /> Download .txt</button><button className={emailSent ? styles.sentConfirmation : styles.sendEmail} onClick={() => void sendEmail()} disabled={emailSending || emailSent}>{emailSending ? <LoaderCircle className={styles.spin} size={17} /> : emailSent ? <Check size={17} /> : <Send size={17} />} {emailSent ? "Email sent" : "Send email"}</button></footer></section></div>}
      </main>
      <MobileNav active="incidents" />
    </div>
  );
}
