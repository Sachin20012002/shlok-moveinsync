"use client";

import { Activity, AlertTriangle, ArrowUpRight, Bot, Building2, Check, ChevronRight, Clock3, Database, Gauge, LoaderCircle, RefreshCw, Route, ShieldAlert, TrendingUp, Users } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getIncidents, getOperationsAnalytics, Incident, OperationsAnalytics } from "./api/client";
import { BrandLockup } from "./components/brand-lockup";
import { MobileNav } from "./components/mobile-nav";
import styles from "./page.module.css";

const EMPTY_ANALYTICS: OperationsAnalytics = {
  availableRange: { startDate: null, endDate: null },
  selectedRange: { startDate: null, endDate: null },
  summary: { completedTrips: 0, delayedTrips: 0, ota: null, affectedEmployees: 0, averageDelayMinutes: 0 },
  vendorPerformance: [], shiftPerformance: [], weeklyTrend: [],
};

const SEVERITY_ORDER: Record<Incident["severity"], number> = { critical: 3, high: 2, warning: 1 };
const VENDOR_COLORS = ["#1f6b55", "#d9933d", "#b7423a", "#327a96", "#7768a6", "#74a35b", "#d2b34c", "#5c706a"];

function displayValue(value: number | null, suffix = "") {
  return value === null ? "Insufficient data" : `${value}${suffix}`;
}

function shortDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString([], { month: "short", day: "numeric" });
}

export default function Home() {
  const [analytics, setAnalytics] = useState(EMPTY_ANALYTICS);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const priorityIncidents = incidents
    .filter((incident) => incident.attentionRequired)
    .sort((left, right) => SEVERITY_ORDER[right.severity] - SEVERITY_ORDER[left.severity] || left.currentValue - right.currentValue)
    .slice(0, 5);

  const weeklyValues = analytics.weeklyTrend.map((week) => week.ota ?? 0);
  const axisMinimum = weeklyValues.length ? Math.max(0, Math.floor(Math.min(...weeklyValues) / 5) * 5 - 5) : 0;
  const axisMaximum = 100;
  const chartLeft = 58;
  const chartRight = 700;
  const chartTop = 24;
  const chartBottom = 210;
  const chartPoints = analytics.weeklyTrend.map((week, index) => {
    const x = chartLeft + (analytics.weeklyTrend.length === 1 ? (chartRight - chartLeft) / 2 : index * (chartRight - chartLeft) / (analytics.weeklyTrend.length - 1));
    const y = chartBottom - (((week.ota ?? axisMinimum) - axisMinimum) / (axisMaximum - axisMinimum || 1)) * (chartBottom - chartTop);
    return { ...week, x, y: Math.min(chartBottom, Math.max(chartTop, y)) };
  });
  const axisTicks = Array.from({ length: 5 }, (_, index) => axisMaximum - index * ((axisMaximum - axisMinimum) / 4));

  const vendorDelayTotal = analytics.vendorPerformance.reduce((total, vendor) => total + vendor.delayedTrips, 0);
  let vendorCursor = 0;
  const vendorSlices = analytics.vendorPerformance.map((vendor, index) => {
    const start = vendorCursor;
    const share = vendorDelayTotal ? vendor.delayedTrips / vendorDelayTotal * 100 : 0;
    vendorCursor += share;
    return { ...vendor, color: VENDOR_COLORS[index % VENDOR_COLORS.length], start, end: vendorCursor, share };
  });
  const donutBackground = vendorSlices.length
    ? `conic-gradient(${vendorSlices.map((vendor) => `${vendor.color} ${vendor.start}% ${vendor.end}%`).join(", ")})`
    : "#e3e9e6";

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [nextAnalytics, nextIncidents] = await Promise.all([getOperationsAnalytics(), getIncidents()]);
      setAnalytics(nextAnalytics);
      setIncidents(nextIncidents);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to reach the backend");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <BrandLockup />
        <nav aria-label="Primary navigation">
          <Link className={styles.navActive} href="/" aria-current="page"><Gauge size={18} /> Operations</Link>
          <Link href="/incidents"><ShieldAlert size={18} /> Incidents</Link>
          <Link href="/agent"><Bot size={18} /> Mobility Agent</Link>
          <Link href="/trips"><Database size={18} /> Data dashboards</Link>
        </nav>
        <div className={styles.persona}><span>Viewing as</span><strong>Transport Manager</strong></div>
      </aside>

      <main className={styles.main}>
        <header className={styles.header}>
          <div><p className={styles.eyebrow}>OVERALL OPERATIONS</p><h1>Mobility control room</h1><p>Service health, priority incidents, and performance across all available trip data.</p></div>
          <button className={styles.iconButton} onClick={() => void refresh()} title="Refresh data" aria-label="Refresh data" disabled={loading}>{loading ? <LoaderCircle className={styles.spin} size={18} /> : <RefreshCw size={18} />}</button>
        </header>

        {error && <div className={styles.error} role="alert"><AlertTriangle size={18} /><span>{error}. Confirm FastAPI is running on port 8000.</span></div>}

        <section className={`${styles.metricBand} ${loading ? styles.metricsLoading : ""}`} aria-label="Overall operational metrics" aria-busy={loading}>
          {loading ? Array.from({ length: 4 }, (_, index) => <article className={styles.metricSkeleton} key={index}><span /><strong /><p /></article>) : <>
            <article className={styles.otaMetric}><div className={styles.metricLabel}><Activity size={18} /> On-time arrival</div><div className={styles.otaRow}><strong>{displayValue(analytics.summary.ota, "%")}</strong><span className={(analytics.summary.ota ?? 0) >= 90 ? styles.healthy : styles.breach}>SLA 90%</span></div><p>Across all completed trips</p></article>
            <article><div className={styles.metricLabel}><Route size={18} /> Completed trips</div><strong>{analytics.summary.completedTrips.toLocaleString()}</strong><p>Overall eligible volume</p></article>
            <article><div className={styles.metricLabel}><Clock3 size={18} /> Delayed trips</div><strong>{analytics.summary.delayedTrips.toLocaleString()}</strong><p>Reported delay above 0 min</p></article>
            <article><div className={styles.metricLabel}><Users size={18} /> Employees affected</div><strong>{analytics.summary.affectedEmployees.toLocaleString()}</strong><p>{analytics.summary.averageDelayMinutes} min average delay</p></article>
          </>}
        </section>

        <section className={styles.operationsSection}>
          <div className={styles.sectionTitle}><div><p className={styles.eyebrow}>PRIORITY QUEUE</p><h2>Incidents needing attention</h2><p className={styles.scopeNote}>Ordered by severity, with critical incidents first.</p></div><span>{priorityIncidents.length} shown</span></div>
          {priorityIncidents.length === 0 ? <div className={styles.empty}><Check size={24} /><strong>No active signals</strong><p>Nothing currently requires acknowledgment.</p></div> : <div className={styles.incidentList}>{priorityIncidents.map((incident) => <Link key={incident.id} className={styles.incidentItem} href={`/incidents?incidentId=${incident.id}`}><span className={`${styles.severity} ${styles[incident.severity]}`}>{incident.severity}</span><strong>{incident.title}</strong><small>{incident.currentValue}% against {incident.slaValue}% SLA</small><p className={styles.incidentAction}><ArrowUpRight size={13} /> {incident.recommendedAction}</p><ChevronRight size={18} /></Link>)}</div>}
          <Link className={styles.viewAll} href="/incidents">View all incidents <ArrowUpRight size={15} /></Link>
        </section>

        <section className={styles.operationsSection}>
          <div className={styles.sectionTitle}><div><p className={styles.eyebrow}>WEEKLY REPORT</p><h2>On-time arrival trend</h2><p className={styles.scopeNote}>Weekly OTA across the full dataset. The vertical axis shows OTA percentage.</p></div><TrendingUp size={20} /></div>
          {chartPoints.length === 0 ? <p className={styles.panelEmpty}>No completed trips available.</p> : <div className={styles.lineChartWrap}><svg className={styles.lineChart} viewBox="0 0 730 270" role="img" aria-label="Weekly on-time arrival line chart"><title>Weekly on-time arrival percentage</title>{axisTicks.map((tick) => { const y = chartBottom - ((tick - axisMinimum) / (axisMaximum - axisMinimum || 1)) * (chartBottom - chartTop); return <g key={tick}><line x1={chartLeft} x2={chartRight} y1={y} y2={y} className={styles.gridLine} /><text x={chartLeft - 12} y={y + 4} textAnchor="end" className={styles.axisText}>{tick.toFixed(0)}%</text></g>; })}<line x1={chartLeft} x2={chartLeft} y1={chartTop} y2={chartBottom} className={styles.axisLine} /><line x1={chartLeft} x2={chartRight} y1={chartBottom} y2={chartBottom} className={styles.axisLine} /><polyline points={chartPoints.map((point) => `${point.x},${point.y}`).join(" ")} className={styles.otaLine} />{chartPoints.map((point) => <g key={point.weekStart}><circle cx={point.x} cy={point.y} r="5" className={styles.otaPoint} /><text x={point.x} y={point.y - 13} textAnchor="middle" className={styles.pointValue}>{point.ota}%</text><text x={point.x} y={chartBottom + 22} textAnchor="middle" className={styles.axisText}>{shortDate(point.weekStart)}</text><text x={point.x} y={chartBottom + 38} textAnchor="middle" className={styles.delayText}>{point.delayedTrips.toLocaleString()} delayed</text></g>)}</svg></div>}
        </section>

        <section className={styles.splitSection}>
          <div className={styles.dataPanel}><div className={styles.sectionTitle}><div><p className={styles.eyebrow}>VENDOR PERFORMANCE</p><h2>Share of delayed trips</h2><p className={styles.scopeNote}>The donut shows how delays are distributed across watched vendors; the legend includes each vendor&apos;s OTA.</p></div><Building2 size={20} /></div><div className={styles.vendorChart}><div className={styles.donut} style={{ background: donutBackground }}><div><strong>{vendorDelayTotal.toLocaleString()}</strong><span>delayed trips</span></div></div><div className={styles.vendorLegend}>{vendorSlices.map((vendor) => <div key={vendor.vendorId}><i style={{ background: vendor.color }} /><span><strong>{vendor.vendorId}</strong><small>{vendor.share.toFixed(1)}% of delays</small></span><b>{displayValue(vendor.ota, "% OTA")}</b></div>)}</div></div></div>
          <div className={styles.dataPanel}><div className={styles.sectionTitle}><div><p className={styles.eyebrow}>SERVICE WINDOWS</p><h2>Shift reliability</h2><p className={styles.scopeNote}>Lowest-reliability shifts appear first so coverage and vendor allocation can be reviewed quickly.</p></div><Users size={20} /></div><div className={styles.shiftList}>{analytics.shiftPerformance.map((shift, index) => { const status = (shift.ota ?? 0) >= 90 ? "stable" : (shift.ota ?? 0) >= 80 ? "watch" : "at risk"; return <div className={styles.shiftRow} key={shift.shiftId}><span className={styles.shiftRank}>{index + 1}</span><div><strong>{shift.shiftId}</strong><small>{shift.completedTrips.toLocaleString()} trips · {shift.delayedTrips.toLocaleString()} delayed</small><div className={styles.shiftTrack}><span style={{ width: `${shift.ota ?? 0}%` }} /></div></div><div><b>{displayValue(shift.ota, "%")}</b><em className={status === "stable" ? styles.stable : status === "watch" ? styles.watch : styles.atRisk}>{status}</em></div></div>; })}</div></div>
        </section>
      </main>
      <MobileNav active="operations" />
    </div>
  );
}
