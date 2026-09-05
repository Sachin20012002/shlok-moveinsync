import { Bot, Gauge, ShieldAlert } from "lucide-react";
import Link from "next/link";
import styles from "./mobile-nav.module.css";

type MobileNavProps = {
  active: "operations" | "incidents" | "agent";
};

export function MobileNav({ active }: MobileNavProps) {
  return (
    <nav className={styles.nav} aria-label="Mobile navigation">
      <Link className={active === "operations" ? styles.active : ""} href="/" aria-current={active === "operations" ? "page" : undefined}>
        <Gauge size={18} /> Operations
      </Link>
      <Link className={active === "incidents" ? styles.active : ""} href="/incidents" aria-current={active === "incidents" ? "page" : undefined}>
        <ShieldAlert size={18} /> Incidents
      </Link>
      <Link className={active === "agent" ? styles.active : ""} href="/agent" aria-current={active === "agent" ? "page" : undefined}>
        <Bot size={18} /> Agent
      </Link>
    </nav>
  );
}