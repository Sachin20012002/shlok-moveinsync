"use client";

import { AlertTriangle, Filter } from "lucide-react";
import { useEffect, useState } from "react";

import { getIncidents } from "@/app/api/client";
import { FeedbackState } from "@/components/FeedbackState";
import { IncidentList } from "@/components/IncidentList";
import type { Incident } from "@/types/api";
import styles from "../page.module.css";

type FilterValue = "attention" | "all" | "acknowledged" | "resolved";

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [filter, setFilter] = useState<FilterValue>("attention");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { let active = true; getIncidents().then((data) => { if (active) setIncidents(data); }).catch((requestError: unknown) => { if (active) setError(requestError instanceof Error ? requestError.message : "Unable to load incidents"); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);

  const filtered = incidents.filter((incident) => filter === "attention" ? incident.attentionRequired : filter === "acknowledged" ? incident.status === "acknowledged" : filter === "resolved" ? incident.status === "resolved" : true);

  return <div className={styles.page}>
    <header className={styles.pageHeader}><div><p className={styles.eyebrow}>Incident management</p><h1>Operational issues</h1><p className={styles.intro}>Prioritized signals, their lifecycle state, and the evidence available for investigation.</p></div></header>
    <div className={styles.filterBar} aria-label="Filter incidents"><span><Filter size={16} />View</span>{(["attention", "all", "acknowledged", "resolved"] as FilterValue[]).map((value) => <button key={value} className={filter === value ? styles.filterActive : undefined} onClick={() => setFilter(value)}>{value === "attention" ? "Needs attention" : value[0].toUpperCase() + value.slice(1)}</button>)}</div>
    {error ? <div className={styles.errorBanner} role="alert"><AlertTriangle size={19} /><div><strong>Incidents could not be loaded</strong><span>{error}</span></div></div> : loading ? <FeedbackState kind="loading" title="Loading incident queue" description="Prioritizing current operational issues." /> : filtered.length === 0 ? <FeedbackState kind="empty" title="No incidents in this view" description="Choose another lifecycle filter or upload new trip data." /> : <IncidentList incidents={filtered} />}
  </div>;
}
