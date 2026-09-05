"use client";

import { AlertTriangle, ArrowDown, ArrowLeft, ArrowUp, Bot, Database, Download, Gauge, MessageSquareText, RefreshCw, Search, ShieldAlert, TableProperties, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { DataDashboard, DataDashboardKind, DashboardQuery, getDataDashboard, getDataDashboardExportUrl } from "../api/client";
import { MobileNav } from "./mobile-nav";
import styles from "./data-dashboard.module.css";

type DashboardConfig = {
  title: string;
  eyebrow: string;
  description: string;
  icon: typeof TableProperties;
  defaultSort: string;
  metrics: Array<{ key: string; label: string; suffix?: string }>;
  filters: Array<{ key: string; label: string; facet?: string; type?: "date" | "text" | "boolean"; options?: Array<[string, string]> }>;
  columns: Array<{ key: string; label: string; sortable?: boolean; format?: "date" | "boolean" | "rating" }>;
};

const CONFIGS: Record<DataDashboardKind, DashboardConfig> = {
  trips: {
    title: "Trip ledger",
    eyebrow: "TRIP OPERATIONS",
    description: "Inspect execution, delay classification, attendance, and compliance directly from the trip records.",
    icon: TableProperties,
    defaultSort: "scheduledArrival",
    metrics: [
      { key: "totalTrips", label: "Total trips" },
      { key: "completedTrips", label: "Completed" },
      { key: "delayedTrips", label: "Reported delayed" },
      { key: "ota", label: "OTA", suffix: "%" },
      { key: "noShows", label: "No-shows" },
      { key: "driverNonCompliance", label: "Driver NC" },
      { key: "affectedEmployees", label: "Employees affected" },
    ],
    filters: [
      { key: "startDate", label: "From", type: "date" },
      { key: "endDate", label: "To", type: "date" },
      { key: "vendor", label: "Vendor", facet: "vendors" },
      { key: "office", label: "Office", facet: "offices" },
      { key: "shift", label: "Shift", facet: "shifts" },
      { key: "status", label: "Status", facet: "statuses" },
      { key: "delayReason", label: "Delay reason", facet: "delayReasons" },
      { key: "delayed", label: "Delay state", type: "boolean", options: [["true", "Delayed"], ["false", "On time"]] },
      { key: "driverNc", label: "Driver NC", type: "boolean" },
      { key: "cabNc", label: "Cab NC", type: "boolean" },
    ],
    columns: [
      { key: "tripId", label: "Trip", sortable: true },
      { key: "scheduledArrival", label: "Scheduled", sortable: true, format: "date" },
      { key: "vendorId", label: "Vendor", sortable: true },
      { key: "officeId", label: "Office", sortable: true },
      { key: "shiftId", label: "Shift", sortable: true },
      { key: "status", label: "Status", sortable: true },
      { key: "employeeCount", label: "Employees" },
      { key: "delayMinutes", label: "Delay min", sortable: true },
      { key: "delayReason", label: "Reason" },
      { key: "noShowCount", label: "No-shows" },
      { key: "driverNonCompliance", label: "Driver NC", format: "boolean" },
      { key: "cabNonCompliance", label: "Cab NC", format: "boolean" },
    ],
  },
  feedback: {
    title: "Feedback signals",
    eyebrow: "RIDER EXPERIENCE",
    description: "Compare route, driver, cab, safety, and marshal ratings with trip context.",
    icon: MessageSquareText,
    defaultSort: "tripAt",
    metrics: [
      { key: "totalResponses", label: "Responses" },
      { key: "averageRouteRating", label: "Route avg", suffix: "/5" },
      { key: "averageDriverRating", label: "Driver avg", suffix: "/5" },
      { key: "averageCabRating", label: "Cab avg", suffix: "/5" },
      { key: "averageSafetyRating", label: "Safety avg", suffix: "/5" },
      { key: "lowRatingCount", label: "Low ratings" },
    ],
    filters: [
      { key: "startDate", label: "From", type: "date" },
      { key: "endDate", label: "To", type: "date" },
      { key: "vendor", label: "Vendor", facet: "vendors" },
      { key: "office", label: "Office", facet: "offices" },
      { key: "tripType", label: "Trip type", facet: "tripTypes" },
      { key: "ratingCategory", label: "Rating field", options: [["route", "Route"], ["driver", "Driver"], ["cab", "Cab"], ["safety", "Safety"], ["marshal", "Marshal"]] },
      { key: "maxRating", label: "Maximum rating", options: [["1", "1 or below"], ["2", "2 or below"], ["3", "3 or below"], ["4", "4 or below"], ["5", "5 or below"]] },
    ],
    columns: [
      { key: "tripId", label: "Trip", sortable: true },
      { key: "tripAt", label: "Trip date", sortable: true, format: "date" },
      { key: "vendorId", label: "Vendor", sortable: true },
      { key: "officeId", label: "Office" },
      { key: "tripType", label: "Type", sortable: true },
      { key: "routeRating", label: "Route", sortable: true, format: "rating" },
      { key: "driverRating", label: "Driver", sortable: true, format: "rating" },
      { key: "cabRating", label: "Cab", sortable: true, format: "rating" },
      { key: "safetyRating", label: "Safety", sortable: true, format: "rating" },
      { key: "marshalRating", label: "Marshal", format: "rating" },
    ],
  },
  "safety-alerts": {
    title: "Safety alert register",
    eyebrow: "SAFETY OPERATIONS",
    description: "Review alert state, severity, acknowledgement, response time, and related trip context.",
    icon: ShieldAlert,
    defaultSort: "startedAt",
    metrics: [
      { key: "totalAlerts", label: "Total alerts" },
      { key: "openAlerts", label: "Open" },
      { key: "criticalAlerts", label: "Critical" },
      { key: "acknowledgedAlerts", label: "Acknowledged" },
      { key: "averageResponseMinutes", label: "Avg response", suffix: " min" },
    ],
    filters: [
      { key: "startDate", label: "From", type: "date" },
      { key: "endDate", label: "To", type: "date" },
      { key: "state", label: "State", facet: "states" },
      { key: "severity", label: "Severity", facet: "severities" },
      { key: "eventType", label: "Event type", facet: "eventTypes" },
      { key: "vendor", label: "Vendor", facet: "vendors" },
      { key: "office", label: "Office", facet: "offices" },
      { key: "source", label: "Source", facet: "sources" },
      { key: "employee", label: "Employee", type: "text" },
    ],
    columns: [
      { key: "eventId", label: "Event", sortable: true },
      { key: "startedAt", label: "Started", sortable: true, format: "date" },
      { key: "eventType", label: "Type", sortable: true },
      { key: "severity", label: "Severity", sortable: true },
      { key: "state", label: "State", sortable: true },
      { key: "tripId", label: "Trip", sortable: true },
      { key: "vendorId", label: "Vendor", sortable: true },
      { key: "officeId", label: "Office" },
      { key: "employeeId", label: "Employee" },
      { key: "source", label: "Source" },
      { key: "acknowledgedAt", label: "Acknowledged", format: "date" },
      { key: "responseMinutes", label: "Response min" },
    ],
  },
};

function initialQuery(config: DashboardConfig): DashboardQuery {
  const query: DashboardQuery = { page: 1, pageSize: 25, sort: config.defaultSort, direction: "desc" };
  if (typeof window !== "undefined") {
    new URLSearchParams(window.location.search).forEach((value, key) => { query[key] = value; });
  }
  return query;
}

function displayValue(value: string | number | boolean | null | undefined, format?: string): string {
  if (value === null || value === undefined || value === "") return "—";
  if (format === "date") return new Date(String(value)).toLocaleString();
  if (format === "boolean") return value ? "Yes" : "No";
  if (format === "rating") return `${value}/5`;
  return typeof value === "number" ? value.toLocaleString() : String(value);
}

export function DataDashboardPage({ kind }: { kind: DataDashboardKind }) {
  const config = CONFIGS[kind];
  const Icon = config.icon;
  const [query, setQuery] = useState<DashboardQuery>(() => initialQuery(config));
  const [data, setData] = useState<DataDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getDataDashboard(kind, query)
      .then((result) => { if (active) setData(result); })
      .catch((requestError) => { if (active) setError(requestError instanceof Error ? requestError.message : "Unable to load dashboard"); })
      .finally(() => { if (active) setLoading(false); });
    const params = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== "") params.set(key, String(value));
    });
    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
    return () => { active = false; };
  }, [kind, query]);

  function update(key: string, value: string | number) {
    setQuery((current) => ({ ...current, [key]: value, page: key === "page" ? value : 1 }));
  }

  function clearFilters() {
    setQuery({ page: 1, pageSize: query.pageSize ?? 25, sort: config.defaultSort, direction: "desc" });
  }

  function changeSort(key: string) {
    setQuery((current) => ({
      ...current,
      page: 1,
      sort: key,
      direction: current.sort === key && current.direction === "desc" ? "asc" : "desc",
    }));
  }

  const currentPage = Number(query.page ?? 1);
  const hasFilters = config.filters.some((filter) => query[filter.key] !== undefined && query[filter.key] !== "");

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}><span>SL</span><strong>SHLOK</strong></div>
        <nav aria-label="Primary navigation">
          <Link href="/"><Gauge size={18} /> Operations</Link>
          <Link href="/incidents"><AlertTriangle size={18} /> Incidents</Link>
          <Link href="/agent"><Bot size={18} /> Mobility Agent</Link>
          <Link className={styles.navActive} href="/trips" aria-current="page"><Database size={18} /> Data dashboards</Link>
        </nav>
        <div className={styles.persona}><span>Viewing as</span><strong>Transport Manager</strong></div>
      </aside>

      <main className={styles.main}>
        <header className={styles.header}>
          <div><Link href="/" className={styles.back}><ArrowLeft size={16} /> Operations</Link><p>{config.eyebrow}</p><h1><Icon size={27} /> {config.title}</h1><span>{config.description}</span></div>
          <div className={styles.headerActions}>
            <button type="button" onClick={() => setQuery((current) => ({ ...current }))} title="Refresh data"><RefreshCw size={17} /> Refresh</button>
            <button type="button" onClick={() => { window.location.href = getDataDashboardExportUrl(kind, query); }} disabled={!data?.rows.length} title="Export all records matching the current filters"><Download size={17} /> Export CSV</button>
          </div>
        </header>

        <nav className={styles.tabs} aria-label="Data dashboards">
          <Link className={kind === "trips" ? styles.tabActive : ""} href="/trips"><TableProperties size={17} /> Trips</Link>
          <Link className={kind === "feedback" ? styles.tabActive : ""} href="/feedback"><MessageSquareText size={17} /> Feedback</Link>
          <Link className={kind === "safety-alerts" ? styles.tabActive : ""} href="/safety-alerts"><ShieldAlert size={17} /> Safety alerts</Link>
        </nav>

        {error && <div className={styles.error} role="alert"><AlertTriangle size={18} /> {error}</div>}

        <section className={`${styles.metrics} ${kind === "trips" ? styles.tripMetrics : ""}`} aria-label="Summary metrics" aria-busy={loading}>
          {config.metrics.map((metric) => <article key={metric.key}><span>{metric.label}</span><strong>{loading && !data ? "—" : displayValue(data?.summary[metric.key])}{data?.summary[metric.key] !== null && data?.summary[metric.key] !== undefined ? metric.suffix : ""}</strong></article>)}
        </section>

        <section className={styles.filterPanel}>
          <div className={styles.filterHeading}><div><Search size={18} /><strong>Filter records</strong></div>{hasFilters && <button type="button" onClick={clearFilters}><X size={15} /> Clear</button>}</div>
          <div className={styles.filters}>
            {config.filters.map((filter) => <label key={filter.key}><span>{filter.label}</span>{filter.type === "date" ? (
              <input type="date" value={String(query[filter.key] ?? "")} onChange={(event) => update(filter.key, event.target.value)} />
            ) : filter.type === "text" ? (
              <input type="search" value={String(query[filter.key] ?? "")} placeholder={`Search ${filter.label.toLowerCase()}`} onChange={(event) => update(filter.key, event.target.value)} />
            ) : (
              <select value={String(query[filter.key] ?? "")} onChange={(event) => update(filter.key, event.target.value)}>
                <option value="">All</option>
                {(filter.options ?? (filter.type === "boolean" ? [["true", "Yes"], ["false", "No"]] : (data?.facets[filter.facet ?? ""] ?? []).map((value) => [value, value] as [string, string]))).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            )}</label>)}
          </div>
        </section>

        <section className={styles.tablePanel} aria-busy={loading}>
          <div className={styles.tableToolbar}><div><strong>{data?.pagination.totalRows.toLocaleString() ?? "—"}</strong><span> matching records</span></div><label>Rows<select value={String(query.pageSize ?? 25)} onChange={(event) => update("pageSize", Number(event.target.value))}><option value="25">25</option><option value="50">50</option><option value="100">100</option></select></label></div>
          <div className={styles.tableWrap}>
            <table>
              <thead><tr>{config.columns.map((column) => <th key={column.key}>{column.sortable ? <button type="button" onClick={() => changeSort(column.key)}>{column.label}{query.sort === column.key ? query.direction === "asc" ? <ArrowUp size={13} /> : <ArrowDown size={13} /> : null}</button> : column.label}</th>)}</tr></thead>
              <tbody>{loading && !data ? <tr><td colSpan={config.columns.length} className={styles.empty}>Loading records…</td></tr> : data?.rows.length ? data.rows.map((row, index) => <tr key={`${String(row[config.columns[0].key])}-${index}`}>{config.columns.map((column) => <td key={column.key} data-label={column.label}>{displayValue(row[column.key], column.format)}</td>)}</tr>) : <tr><td colSpan={config.columns.length} className={styles.empty}>No records match these filters.</td></tr>}</tbody>
            </table>
          </div>
          <div className={styles.pagination}><span>Page {data?.pagination.page ?? currentPage} of {data?.pagination.totalPages ?? 1}</span><div><button type="button" disabled={currentPage <= 1 || loading} onClick={() => update("page", currentPage - 1)}>Previous</button><button type="button" disabled={currentPage >= (data?.pagination.totalPages ?? 1) || loading} onClick={() => update("page", currentPage + 1)}>Next</button></div></div>
        </section>
      </main>
      <MobileNav active="data" />
    </div>
  );
}
