import { ArrowUpRight, CheckCircle2, Clock3, Database, MapPin, ShieldAlert } from "lucide-react";
import Link from "next/link";

import type { Operations } from "@/types/api";
import styles from "./decision-desk.module.css";

function pretty(value: string) { return value.replaceAll("_", " "); }

export function OperationsPanels({ operations }: { operations: Operations }) {
  return (
    <div className={styles.panelGrid}>
      <section className={styles.tripPanel} aria-labelledby="exceptions-title">
        <div className={styles.panelHeading}><div><p>Live evidence</p><h2 id="exceptions-title">Trip exceptions</h2></div><span>{operations.tripExceptions.length} flagged</span></div>
        {operations.tripExceptions.length === 0 ? <div className={styles.emptyPanel}><CheckCircle2 size={22} /><span>No trip exceptions in the latest dataset.</span></div> : (
          <div className={styles.exceptionList}>{operations.tripExceptions.slice(0, 6).map((trip) => {
            const incidentId = trip.relatedIncidentIds[0];
            const content = <><div className={styles.tripIdentity}><strong>{trip.tripId}</strong><span>{trip.vendorId} · {trip.routeId}</span></div><div className={styles.tripIssue}><strong>{pretty(trip.issue)}</strong><span>{trip.delayMinutes === null ? "Delay unavailable" : `${trip.delayMinutes} min delay`} · Employee {trip.employeeId}</span></div><p>{trip.recommendedAction}</p>{incidentId && <ArrowUpRight size={17} />}</>;
            return incidentId ? <Link key={trip.tripId} href={`/incidents/${incidentId}`} className={styles.exceptionRow}>{content}</Link> : <div key={trip.tripId} className={styles.exceptionRow}>{content}</div>;
          })}</div>
        )}
      </section>

      <section className={styles.shiftPanel} aria-labelledby="shifts-title">
        <div className={styles.panelHeading}><div><p>Service lanes</p><h2 id="shifts-title">Shift readiness</h2></div></div>
        <div className={styles.shiftList}>{operations.shiftReadiness.length === 0 ? <div className={styles.emptyPanel}>No shift data available.</div> : operations.shiftReadiness.map((shift) => (
          <article key={shift.shiftId}>
            <div><strong>{shift.shiftId}</strong><span className={styles[shift.status]}>{pretty(shift.status)}</span></div>
            <div className={styles.shiftStats}><span><b>{shift.completedTrips}</b> completed</span><span><b>{shift.delayedTrips}</b> delayed</span><span><b>{shift.affectedEmployees}</b> affected</span></div>
          </article>
        ))}</div>
      </section>

      <section className={styles.watchPanel} aria-labelledby="watch-title">
        <div className={styles.panelHeading}><div><p>Partner signal</p><h2 id="watch-title">Vendor watch</h2></div></div>
        <div className={styles.vendorList}>{operations.vendorWatchlist.length === 0 ? <div className={styles.emptyPanel}>No vendor risk detected.</div> : operations.vendorWatchlist.slice(0, 4).map((vendor) => (
          <div key={vendor.vendorId}><span className={styles.vendorMark}><MapPin size={15} /></span><div><strong>{vendor.vendorId}</strong><span>{vendor.delayedTrips} delayed · {vendor.missingGps} missing GPS</span></div><b>{vendor.ota}%<small> OTA</small></b></div>
        ))}</div>
      </section>

      <section className={styles.qualityPanel} aria-labelledby="quality-title">
        <div className={styles.panelHeading}><div><p>Trust layer</p><h2 id="quality-title">Data quality</h2></div><Database size={18} /></div>
        <div className={styles.qualityGrid}><div><span>Missing GPS</span><strong>{operations.dataQuality.missingGps}</strong></div><div><span>Missing arrivals</span><strong>{operations.dataQuality.missingArrivals}</strong></div><div><span>Invalid rows</span><strong>{operations.dataQuality.invalidRows}</strong></div><div><span>Skipped rows</span><strong>{operations.dataQuality.skippedRows}</strong></div></div>
        <p className={styles.lastUpdate}><Clock3 size={14} />{operations.dataQuality.lastDataUpdate ? `Updated ${new Date(operations.dataQuality.lastDataUpdate).toLocaleString()}` : "No dataset timestamp available"}</p>
        {(operations.dataQuality.invalidRows > 0 || operations.dataQuality.skippedRows > 0) && <div className={styles.qualityNote}><ShieldAlert size={16} />Exceptions remain visible; official metrics use validated rows only.</div>}
      </section>
    </div>
  );
}
