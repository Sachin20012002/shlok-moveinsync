"use client";

import { AlertTriangle, ArrowUpRight, BellRing, CheckCircle2, CircleAlert, Filter, Lightbulb } from "lucide-react";
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

  const attentionCount = incidents.filter((incident) => incident.attentionRequired).length;
  const criticalCount = incidents.filter((incident) => incident.severity === "critical").length;
  const resolvedCount = incidents.filter((incident) => incident.status === "resolved").length;

  return <div className={styles.page}>
    <header className={styles.pageHeader}><div><p className={styles.eyebrow}>Operational intelligence</p><h1>Insights</h1><p className={styles.intro}>Prioritized signals, lifecycle context, and the evidence managers need to decide what happens next.</p></div></header>
    <section className={styles.insightOverview} aria-label="Insights overview">
      <div className={styles.insightStat}><span className={styles.insightIcon}><Lightbulb size={17} /></span><div><strong>{incidents.length}</strong><small>Total insights</small></div></div>
      <div className={`${styles.insightStat} ${styles.insightWarning}`}><span className={styles.insightIcon}><BellRing size={17} /></span><div><strong>{attentionCount}</strong><small>Needs attention</small></div></div>
      <div className={`${styles.insightStat} ${styles.insightCritical}`}><span className={styles.insightIcon}><CircleAlert size={17} /></span><div><strong>{criticalCount}</strong><small>Critical signals</small></div></div>
      <div className={`${styles.insightStat} ${styles.insightResolved}`}><span className={styles.insightIcon}><CheckCircle2 size={17} /></span><div><strong>{resolvedCount}</strong><small>Resolved</small></div></div>
    </section>
    <div className={styles.filterBar} aria-label="Filter insights"><span><Filter size={16} />View</span>{(["attention", "all", "acknowledged", "resolved"] as FilterValue[]).map((value) => <button key={value} className={filter === value ? styles.filterActive : undefined} onClick={() => setFilter(value)}>{value === "attention" ? "Needs attention" : value === "all" ? "All insights" : value[0].toUpperCase() + value.slice(1)}</button>)}</div>
    {error ? <div className={styles.errorBanner} role="alert"><AlertTriangle size={19} /><div><strong>Insights could not be loaded</strong><span>{error}</span></div></div> : loading ? <FeedbackState kind="loading" title="Loading insights" description="Prioritizing current operational signals." /> : filtered.length === 0 ? <FeedbackState kind="empty" title="No insights in this view" description="Choose another lifecycle filter or upload new trip data." /> : <section className={styles.insightQueue}>
      <header className={styles.queueHeader}><div><p className={styles.queueEyebrow}>Priority queue</p><h2>{filter === "attention" ? `${filtered.length} issues need your attention` : `${filtered.length} insights`}</h2></div>{filter === "attention" && <button type="button" onClick={() => setFilter("all")}>View all <ArrowUpRight size={14} /></button>}</header>
      <IncidentList incidents={filtered} />
    </section>}
  </div>;
}
