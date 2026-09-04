import { BellRing, CheckCircle2, CircleDot, RotateCcw, TrendingUp } from "lucide-react";

import type { IncidentEvent } from "@/types/api";
import styles from "./operations.module.css";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

const eventPresentation: Record<string, { label: string; icon: typeof CircleDot }> = {
  opened: { label: "Issue detected", icon: CircleDot },
  escalated: { label: "Severity escalated", icon: TrendingUp },
  acknowledged: { label: "Manager acknowledged", icon: CheckCircle2 },
  reopened: { label: "Manager attention requested again", icon: BellRing },
  resolved: { label: "Performance recovered", icon: RotateCcw },
};

export function IncidentTimeline({ events }: { events: IncidentEvent[] }) {
  return (
    <section className={styles.timelineSection} aria-labelledby="lifecycle-heading">
      <div className={styles.sectionTitle}><p>Incident lifecycle</p><h2 id="lifecycle-heading">From detection to decision</h2></div>
      {events.length === 0 ? <p className={styles.timelineEmpty}>No lifecycle events are available.</p> : (
        <ol className={styles.timeline}>
          {events.map((event, index) => {
            const presentation = eventPresentation[event.eventType] ?? { label: event.eventType.replaceAll("_", " "), icon: CircleDot };
            const Icon = presentation.icon;
            return (
              <li key={event.id} className={styles.timelineItem}>
                <span className={styles.timelineMarker}><Icon size={17} aria-hidden="true" /></span>
                <div className={styles.timelineContent}>
                  <div><strong>{presentation.label}</strong><time dateTime={event.createdAt}>{formatDate(event.createdAt)}</time></div>
                  <p>{event.message}</p>
                  <span>Metric at event: {event.metricValue}%</span>
                </div>
                {index < events.length - 1 && <span className={styles.timelineLine} aria-hidden="true" />}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
