"use client";

import { AlertTriangle, Building2, Check, Clock3, Route, Users } from "lucide-react";
import { useState } from "react";

import type { Incident } from "@/types/api";
import { SeverityBadge, StatusBadge } from "./StatusBadge";
import styles from "./operations.module.css";

type Props = { incident: Incident; onAcknowledge: () => Promise<void> };

export function IncidentDetail({ incident, onAcknowledge }: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gap = incident.currentValue - incident.slaValue;

  async function acknowledge() {
    setSubmitting(true);
    setError(null);
    try {
      await onAcknowledge();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The incident could not be acknowledged.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.detailStack}>
      <section className={styles.detailHero}>
        <div className={styles.detailHeroTop}><div><SeverityBadge severity={incident.severity} /><StatusBadge status={incident.status} /></div>{incident.attentionRequired && <span className={styles.actionRequired}>Manager action required</span>}</div>
        <h1>{incident.title}</h1>
        <p>{incident.reason}</p>
        <div className={styles.comparisonGrid}>
          <div><span>Current</span><strong>{incident.currentValue}%</strong></div>
          <div><span>SLA target</span><strong>{incident.slaValue}%</strong></div>
          <div><span>Gap</span><strong className={gap < 0 ? styles.negative : undefined}>{gap.toFixed(1)} pp</strong></div>
          <div><span>Previous reading</span><strong>{incident.previousValue === null ? "Unavailable" : `${incident.previousValue}%`}</strong></div>
        </div>
      </section>

      {incident.status === "reopened" && <div className={styles.reopenedNotice}><AlertTriangle size={20} aria-hidden="true" /><div><strong>Re-acknowledgment is required</strong><p>The incident worsened after acknowledgment at {incident.acknowledgedValue ?? "an earlier"}%. This is notification #{incident.notificationCount}.</p></div></div>}

      <section className={styles.evidenceSection} aria-labelledby="evidence-heading">
        <div className={styles.sectionTitle}><p>Evidence and impact</p><h2 id="evidence-heading">What the data shows</h2></div>
        <div className={styles.evidenceGrid}>
          <div><Users size={19} aria-hidden="true" /><span>Affected employees</span><strong>{incident.affectedEmployees}</strong></div>
          <div><Building2 size={19} aria-hidden="true" /><span>Contributing vendor</span><strong>{incident.contributingVendor ?? "Not identified"}</strong></div>
          <div><Route size={19} aria-hidden="true" /><span>Contributing route</span><strong>{incident.contributingRoute ?? "Not identified"}</strong></div>
          <div><Clock3 size={19} aria-hidden="true" /><span>Contributing shift</span><strong>{incident.contributingShift ?? "Not identified"}</strong></div>
        </div>
        {incident.dataQualityWarning && <div className={styles.dataWarning}><AlertTriangle size={18} aria-hidden="true" /><span>{incident.dataQualityWarning}</span></div>}
      </section>

      <section className={styles.recommendationSection} aria-labelledby="recommendation-heading">
        <div><p>Recommended next action</p><h2 id="recommendation-heading">Turn the signal into a response</h2><span>This recommendation comes from the current deterministic incident rules and supporting data.</span></div>
        <div className={styles.recommendationBody}><Check size={21} aria-hidden="true" /><p>{incident.recommendedAction}</p></div>
        <button onClick={() => void acknowledge()} disabled={!incident.attentionRequired || submitting}>
          <Check size={18} aria-hidden="true" />
          {submitting ? "Recording decision…" : incident.status === "reopened" ? "Re-acknowledge incident" : incident.attentionRequired ? "Acknowledge incident" : "Incident acknowledged"}
        </button>
        {error && <p className={styles.actionError} role="alert">{error}</p>}
      </section>
    </div>
  );
}
