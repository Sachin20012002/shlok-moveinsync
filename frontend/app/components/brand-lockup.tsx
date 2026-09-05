import Image from "next/image";
import Link from "next/link";
import styles from "./brand-lockup.module.css";

export function BrandLockup() {
  return (
    <Link className={styles.brand} href="/" aria-label="MoveInSync mobility control room, built by Team SHLOK">
      <span className={styles.logoPanel}>
        <Image
          src="/brand/moveinsync-logo.svg"
          alt="MoveInSync"
          width={113}
          height={45}
          priority
        />
      </span>
      <span className={styles.team}>Built by <strong>Team SHLOK</strong></span>
    </Link>
  );
}
