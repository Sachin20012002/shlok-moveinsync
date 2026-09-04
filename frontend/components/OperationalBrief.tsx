import { ArrowRight, CircleAlert, Radar, Route, Users } from "lucide-react";
import Link from "next/link";

import type { Dashboard, Incident, Operations } from "@/types/api";
import styles from "./decision-desk.module.css";

export function OperationalBrief({ dashboard, operations, incident }: { dashboard: Dashboard; operations: Operations; incident?: Incident }) {
  const recommendation = operations.recommendedActions.find((item) => item.incidentId === incident?.id)?.action ?? incident?.recommendedAction;
  const breach = dashboard.onTimeArrival.value === null ? "Awaiting trip data" : `${dashboard.onTimeArrival.value}% OTA vs ${dashboard.onTimeArrival.sla}% SLA`;

  return (
    <section className={styles.brief} aria-labelledby="brief-title">
      <div className={styles.briefLead}>
        <span className={incident ? styles.signalCritical : styles.signalClear}><Radar size={16} />{incident ? "Manager attention required" : "No active operational breach"}</span>
        <p className={styles.briefKicker}>Operational brief</p>
        <h2 id="brief-title">{incident?.title ?? "Mobility operations are within current thresholds"}</h2>
        <p>{incident?.reason ?? "The latest evaluated dataset has not produced an incident requiring manager action."}</p>
        {incident && <Link href={`/incidents/${incident.id}`}>Open investigation <ArrowRight size={17} /></Link>}
      </div>
      <div className={styles.evidenceSpine} aria-label="Decision evidence">
        <div><span><CircleAlert size={15} /> Signal</span><strong>{breach}</strong></div>
        <div><span><Route size={15} /> Contributor</span><strong>{incident?.contributingRoute ?? incident?.contributingVendor ?? "No contributor isolated"}</strong></div>
        <div><span><Users size={15} /> Impact</span><strong>{incident ? `${incident.affectedEmployees} employees affected` : `${operations.activeTrips} active trips`}</strong></div>
        <div className={styles.nextDecision}><span>Recommended decision</span><strong>{recommendation ?? "Continue monitoring current service levels."}</strong></div>
      </div>
    </section>
  );
}
