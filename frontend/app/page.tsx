"use client";

import { useEffect, useState } from "react";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function Home() {
  const [backendStatus, setBackendStatus] = useState(
    API_URL ? "Loading..." : "Unavailable",
  );

  useEffect(() => {
    if (!API_URL) {
      return;
    }

    const healthUrl = `${API_URL.replace(/\/$/, "")}/health`;
    const controller = new AbortController();

    async function checkBackend() {
      try {
        const response = await fetch(healthUrl, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Backend returned ${response.status}`);
        }

        const data: unknown = await response.json();

        if (
          typeof data !== "object" ||
          data === null ||
          !("status" in data) ||
          typeof data.status !== "string"
        ) {
          throw new Error("Backend returned an invalid health response");
        }

        setBackendStatus(data.status);
      } catch {
        if (!controller.signal.aborted) {
          setBackendStatus("Unavailable");
        }
      }
    }

    void checkBackend();

    return () => controller.abort();
  }, []);

  return (
    <main className={styles.main}>
      <h1>SHLOK</h1>
      <p className={styles.subtitle}>MoveInSync Hackathon</p>
      <p className={styles.status}>Backend Status: {backendStatus}</p>
    </main>
  );
}
