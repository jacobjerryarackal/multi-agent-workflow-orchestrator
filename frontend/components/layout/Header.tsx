"use client";

import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { getSystemHealth } from "@/lib/api/health";
import { Badge } from "@/components/ui/Badge";
import { Database, Cpu, ShieldCheck } from "lucide-react";
import { HealthResponse } from "@/lib/types/api";

export function Header() {
  const pathname = usePathname();
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function fetchHealth() {
      try {
        const data = await getSystemHealth();
        if (isMounted) setHealth(data);
      } catch {
        if (isMounted) setHealth(null);
      }
    }
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const getBreadcrumb = () => {
    if (pathname === "/") return "Operations Console";
    const parts = pathname.split("/").filter(Boolean);
    return parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(" / ");
  };

  return (
    <header className="h-14 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur px-6 flex items-center justify-between shrink-0 sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <span className="text-xs font-mono-data text-zinc-500 uppercase">
          CLUSTER
        </span>
        <span className="text-zinc-600">/</span>
        <span className="text-xs font-medium text-zinc-200">{getBreadcrumb()}</span>
      </div>

      <div className="flex items-center gap-4 text-xs font-mono-data">
        {health ? (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-zinc-400">
              <Database className="w-3.5 h-3.5 text-zinc-400" />
              <span>
                PG 16:{" "}
                <strong
                  className={
                    health.components?.database?.status === "healthy"
                      ? "text-emerald-400"
                      : "text-rose-400"
                  }
                >
                  {health.components?.database?.status || "unknown"}
                </strong>
              </span>
            </div>

            <div className="flex items-center gap-1.5 text-zinc-400">
              <Cpu className="w-3.5 h-3.5 text-zinc-400" />
              <span>
                Agents:{" "}
                <strong className="text-zinc-200">
                  {typeof health.components?.agent_registry?.details === "object" &&
                  health.components?.agent_registry?.details &&
                  "registered_count" in health.components.agent_registry.details
                    ? String(health.components.agent_registry.details.registered_count)
                    : "5"}
                </strong>
              </span>
            </div>

            <Badge
              variant={
                health.status === "healthy"
                  ? "success"
                  : health.status === "degraded"
                  ? "warning"
                  : "danger"
              }
              dot
            >
              {health.status.toUpperCase()}
            </Badge>
          </div>
        ) : (
          <Badge variant="neutral" dot>
            CONNECTING...
          </Badge>
        )}
      </div>
    </header>
  );
}
