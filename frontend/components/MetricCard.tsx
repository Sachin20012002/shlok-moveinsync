import type { ReactNode } from "react";

import styles from "./operations.module.css";

type Props = {
  label: string;
  value: string;
  detail: string;
  reference?: string;
  icon: ReactNode;
  tone?: "neutral" | "healthy" | "warning" | "critical";
  featured?: boolean;
};

export function MetricCard({ label, value, detail, reference, icon, tone = "neutral", featured = false }: Props) {
  return (
    <article className={`${styles.metricCard} ${featured ? styles.metricFeatured : ""} ${styles[tone]}`}>
      <div className={styles.metricLabel}><span>{icon}</span>{label}</div>
      <div className={styles.metricValueRow}><strong>{value}</strong>{reference && <span>{reference}</span>}</div>
      <p>{detail}</p>
    </article>
  );
}
