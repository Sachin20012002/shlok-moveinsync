"use client";

import { AlertTriangle, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { acknowledgeIncident, getIncident, getIncidentEvents } from "@/app/api/client";
import { FeedbackState } from "@/components/FeedbackState";
import { IncidentDetail } from "@/components/IncidentDetail";
import { IncidentTimeline } from "@/components/IncidentTimeline";
import type { Incident, IncidentEvent } from "@/types/api";

import styles from "../../page.module.css";

export default function InvestigationPage() {
  const params = useParams<{ id: string }>();
  const incidentId = Number(params.id);
  const [incident, setIncident] = useState<Incident | null>(null);
  const [events, setEvents] = useState<IncidentEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function applyInvestigation([nextIncident, nextEvents]: [Incident, IncidentEvent[]]) {
    setIncident(nextIncident);
    setEvents(nextEvents);
  }

  useEffect(() => {
    let active = true;
    if (!Number.isFinite(incidentId)) {
      return () => { active = false; };
    }
    Promise.all([getIncident(incidentId), getIncidentEvents(incidentId)])
      .then((data) => { if (active) applyInvestigation(data); })
      .catch((requestError: unknown) => { if (active) setError(requestError instanceof Error ? requestError.message : "Unable to load the investigation"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [incidentId]);

  async function acknowledge() {
    await acknowledgeIncident(incidentId);
    applyInvestigation(await Promise.all([getIncident(incidentId), getIncidentEvents(incidentId)]));
  }

  return (
    <div className={styles.page}>
      <Link className={styles.backLink} href="/incidents"><ArrowLeft size={16} aria-hidden="true" />Back to incidents</Link>
      <header className={styles.investigationHeader}><p className={styles.eyebrow}>Incident investigation</p><h2>Evidence, context, and manager decision</h2></header>
      {error ? <div className={styles.errorBanner} role="alert"><AlertTriangle size={19} aria-hidden="true" /><div><strong>Investigation could not be loaded</strong><span>{error}</span></div></div> : loading ? <FeedbackState kind="loading" title="Building the investigation" description="Loading current evidence and lifecycle events." /> : incident ? <div className={styles.investigationGrid}><IncidentDetail incident={incident} onAcknowledge={acknowledge} /><IncidentTimeline events={events} /></div> : <FeedbackState kind="empty" title="Incident not found" description="Return to the incident queue and select another issue." />}
    </div>
  );
}
