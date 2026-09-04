"use client";

import { Activity, ArrowLeft, Building2, Check, Clock3, Gauge, Route, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { acknowledgeIncident, getIncidentEvents, getIncidents, Incident, IncidentEvent } from "../api/client";
import styles from "./incidents.module.css";

type Filter = "all" | Incident["status"];

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [events, setEvents] = useState<IncidentEvent[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<string | null>(null);
  const filtered = filter === "all" ? incidents : incidents.filter((incident) => incident.status === filter);
  const selected = filtered.find((incident) => incident.id === selectedId) ?? filtered[0];

  async function loadIncidents() {
    try {
      const next = await getIncidents();
      setIncidents(next);
      setSelectedId((current) => next.some((item) => item.id === current) ? current : (next[0]?.id ?? null));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load incidents");
    }
  }

  useEffect(() => { void loadIncidents(); }, []);
  useEffect(() => {
    if (!selected) { setEvents([]); return; }
    void getIncidentEvents(selected.id).then(setEvents).catch(() => setEvents([]));
  }, [selected?.id]);

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

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}><span>SL</span><strong>SHLOK</strong></div>
        <nav aria-label="Primary navigation">
          <Link href="/"><Gauge size={18} /> Operations</Link>
          <Link className={styles.navActive} href="/incidents"><ShieldAlert size={18} /> Incidents</Link>
          <button disabled title="Vendor workspace coming soon"><Building2 size={18} /> Vendors</button>
          <button disabled title="Route workspace coming soon"><Route size={18} /> Routes</button>
        </nav>
        <div className={styles.persona}><span>Viewing as</span><strong>Transport Manager</strong></div>
      </aside>
      <main className={styles.page}>
        <header><Link className={styles.backLink} href="/"><ArrowLeft size={17} /> Operations</Link><p>INCIDENT WORKSPACE</p><h1>Incident lifecycle</h1><span>Review every signal, acknowledgment, escalation, and recovery.</span></header>
        {error && <div className={styles.error}>{error}</div>}
        <div className={styles.filters}>{(["all", "open", "reopened", "acknowledged", "resolved"] as Filter[]).map((value) => <button key={value} className={filter === value ? styles.filterActive : ""} onClick={() => setFilter(value)}>{value} <span>{value === "all" ? incidents.length : incidents.filter((item) => item.status === value).length}</span></button>)}</div>
        <section className={styles.workspace}>
          <div className={styles.list}>{filtered.length === 0 ? <p className={styles.empty}>No incidents match this filter.</p> : filtered.map((incident) => <button key={incident.id} className={selected?.id === incident.id ? styles.selected : ""} onClick={() => setSelectedId(incident.id)}><span className={`${styles.severity} ${styles[incident.severity]}`}>{incident.severity}</span><strong>{incident.title}</strong><small>{incident.currentValue}% / {incident.slaValue}% SLA</small><em>{incident.status}</em></button>)}</div>
          <article className={styles.detail}>{!selected ? <div className={styles.empty}>Select an incident.</div> : <><div className={styles.detailHead}><div><span className={`${styles.severity} ${styles[selected.severity]}`}>{selected.severity}</span><h2>{selected.title}</h2></div><strong>{selected.status}</strong></div><div className={styles.values}><div><span>Current</span><strong>{selected.currentValue}%</strong></div><div><span>Acknowledged at</span><strong>{selected.acknowledgedValue === null ? "Not yet" : `${selected.acknowledgedValue}%`}</strong></div><div><span>Notifications</span><strong>{selected.notificationCount}</strong></div></div><p className={styles.reason}>{selected.reason}</p><div className={styles.action}><span>Recommended action</span><p>{selected.recommendedAction}</p></div>{selected.attentionRequired && <button className={styles.ack} onClick={() => void acknowledge()}><Check size={17} /> {selected.status === "reopened" ? "Re-acknowledge" : "Acknowledge"}</button>}<div className={styles.history}><h3><Clock3 size={17} /> Lifecycle history</h3>{events.map((event) => <div key={event.id}><Activity size={14} /><time>{new Date(event.createdAt).toLocaleString()}</time><strong>{event.eventType}</strong><p>{event.message}</p></div>)}</div></>}</article>
        </section>
      </main>
    </div>
  );
}