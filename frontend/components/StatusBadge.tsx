import type { IncidentSeverity, IncidentStatus } from "@/types/api";

import styles from "./operations.module.css";

export function SeverityBadge({ severity }: { severity: IncidentSeverity }) {
  return <span className={`${styles.badge} ${styles[`severity_${severity}`]}`}>{severity}</span>;
}

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return <span className={`${styles.statusBadge} ${styles[`status_${status}`]}`}>{status}</span>;
}
