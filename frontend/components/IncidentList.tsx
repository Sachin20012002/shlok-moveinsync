import { ArrowUpRight, BellRing } from "lucide-react";
import Link from "next/link";

import type { Incident } from "@/types/api";
import { SeverityBadge, StatusBadge } from "./StatusBadge";
import styles from "./operations.module.css";

export function IncidentList({ incidents }: { incidents: Incident[] }) {
  return (
    <div className={styles.incidentList}>
      {incidents.map((incident) => (
        <Link className={`${styles.incidentCard} ${styles[`incidentCard_${incident.severity}`]}`} href={`/incidents/${incident.id}`} key={incident.id}>
          <div className={styles.incidentTopline}>
            <div><SeverityBadge severity={incident.severity} /><StatusBadge status={incident.status} /></div>
            {incident.attentionRequired && <span className={styles.attentionLabel}><BellRing size={14} aria-hidden="true" />Action required</span>}
          </div>
          <div className={styles.incidentBody}>
            <div><h3>{incident.title}</h3><p>{incident.reason}</p></div>
            <div className={styles.incidentMetric}><strong>{incident.currentValue}%</strong><span>Target {incident.slaValue}%</span></div>
          </div>
          <div className={styles.incidentFooter}>
            <span>{incident.affectedEmployees} employees affected</span>
            <strong>Investigate <ArrowUpRight size={15} aria-hidden="true" /></strong>
          </div>
        </Link>
      ))}
    </div>
  );
}
