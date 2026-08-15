"use client";

import { useEffect, useState } from "react";

interface HealthServices {
  api: string;
  postgres: string;
  redis: string;
  object_storage: string;
}

interface HealthResponse {
  status: string;
  services: HealthServices;
}

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchHealth() {
      try {
        const res = await fetch("http://localhost:8000/api/v1/health/ready");
        const data = await res.json();
        setHealth(data);
      } catch (error) {
        setHealth({
          status: "offline",
          services: {
            api: "offline",
            postgres: "unknown",
            redis: "unknown",
            object_storage: "unknown",
          },
        });
      } finally {
        setLoading(false);
      }
    }

    fetchHealth();
  }, []);

  return (
    <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Canlı Öğretmen AI</h1>
      <h2>System Status</h2>

      <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <div>
          <strong>Frontend:</strong> Online
        </div>
        <div>
          <strong>API:</strong> {loading ? "Checking..." : health?.services?.api === "ok" ? "Online" : "Offline"}
        </div>
        <div>
          <strong>Database:</strong> {loading ? "Checking..." : health?.services?.postgres === "ok" ? "Online" : health?.services?.postgres === "error" ? "Error" : "Offline"}
        </div>
        <div>
          <strong>Redis:</strong> {loading ? "Checking..." : health?.services?.redis === "ok" ? "Online" : health?.services?.redis === "error" ? "Error" : "Offline"}
        </div>
        <div>
          <strong>Storage:</strong> {loading ? "Checking..." : health?.services?.object_storage === "ok" ? "Online" : health?.services?.object_storage === "error" ? "Error" : "Offline"}
        </div>
      </div>
    </main>
  );
}
