"use client";

import { Activity, BellRing } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import styles from "./AppShell.module.css";

const navigation = [
  { href: "/", label: "Operations", icon: Activity },
  { href: "/incidents", label: "Incidents", icon: BellRing },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <Link className={styles.brand} href="/" aria-label="SHLOK operations home">
          <span className={styles.mark}>SL</span>
          <span><strong>SHLOK</strong><small>Mobility intelligence</small></span>
        </Link>
        <nav aria-label="Primary navigation">
          {navigation.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return <Link key={href} href={href} className={active ? styles.active : undefined} aria-current={active ? "page" : undefined}><Icon size={19} aria-hidden="true" /><span>{label}</span></Link>;
          })}
        </nav>
        <div className={styles.persona}><span>Workspace</span><strong>Transport Manager</strong></div>
      </aside>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
