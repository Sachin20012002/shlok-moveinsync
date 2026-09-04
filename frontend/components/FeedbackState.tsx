import { CheckCircle2, LoaderCircle, SearchX } from "lucide-react";

import styles from "./operations.module.css";

type Props = { kind: "loading" | "empty" | "success"; title: string; description: string };

export function FeedbackState({ kind, title, description }: Props) {
  const Icon = kind === "loading" ? LoaderCircle : kind === "success" ? CheckCircle2 : SearchX;
  return <div className={styles.feedback}><Icon className={kind === "loading" ? styles.spin : undefined} size={25} aria-hidden="true" /><strong>{title}</strong><p>{description}</p></div>;
}
