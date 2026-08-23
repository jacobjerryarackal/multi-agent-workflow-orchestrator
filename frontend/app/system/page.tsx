"use client";

import React, { useEffect, useState } from "react";
import { getSystemHealth } from "@/lib/api/health";
import { HealthResponse } from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { LoadingState, ErrorState } from "@/components/ui/LoadingState";
import { formatDate } from "@/lib/utils/formatting";
import { Server, Database, Cpu, ShieldCheck, RefreshCw, Activity, Terminal } from "lucide-react";

export default function SystemHealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadHealth = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getSystemHealth();
      setHealth(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to query system health endpoint.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
            <Server className="w-5 h-5 text-zinc-300" />
            System Health & Telemetry
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Operational status of PostgreSQL persistence, Gemini LLM provider, agent registry, and middleware security.
          </p>
        </div>

        <Button variant="secondary" size="sm" onClick={loadHealth} isLoading={isLoading}>
          <RefreshCw className="w-3.5 h-3.5" />
          Poll Health
        </Button>
      </div>

      {isLoading && !health ? (
        <LoadingState message="Polling cluster health telemetry..." />
      ) : error && !health ? (
        <ErrorState title="Telemetry Unreachable" error={error} onRetry={loadHealth} />
      ) : health ? (
        <div className="flex flex-col gap-6">
          {/* Overall Health Status Banner */}
          <div className="p-4 rounded-lg border border-zinc-800 bg-zinc-900/60 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-emerald-950/60 border border-emerald-800 flex items-center justify-center text-emerald-400">
                <Activity className="w-5 h-5" />
              </div>
              <div>
                <span className="text-xs font-mono-data text-zinc-400 uppercase">
                  ORCHESTRATOR STATUS
                </span>
                <div className="text-base font-bold text-zinc-100">
                  {health.status.toUpperCase()}
                </div>
              </div>
            </div>

            <div className="text-right text-xs font-mono-data text-zinc-400">
              <div>Version: <strong className="text-zinc-200">{health.version}</strong></div>
              <div>Last ping: {formatDate(health.timestamp, { includeTime: true })}</div>
            </div>
          </div>

          {/* Component breakdowns */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Database component */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-zinc-400" />
                  <CardTitle className="text-sm">PostgreSQL 16</CardTitle>
                </div>
                <Badge
                  variant={
                    health.components?.database?.status === "healthy"
                      ? "success"
                      : "danger"
                  }
                  dot
                >
                  {health.components?.database?.status?.toUpperCase() || "UNKNOWN"}
                </Badge>
              </CardHeader>
              <CardContent className="pt-1 text-xs">
                <p className="text-zinc-400 leading-relaxed">
                  Transactional ACID state persistence, row-level task claiming (SELECT FOR UPDATE), and audit event persistence.
                </p>
              </CardContent>
            </Card>

            {/* Agent Registry */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-zinc-400" />
                  <CardTitle className="text-sm">Agent Registry</CardTitle>
                </div>
                <Badge
                  variant={
                    health.components?.agent_registry?.status === "healthy"
                      ? "success"
                      : "danger"
                  }
                  dot
                >
                  {health.components?.agent_registry?.status?.toUpperCase() || "UNKNOWN"}
                </Badge>
              </CardHeader>
              <CardContent className="pt-1 text-xs">
                <p className="text-zinc-400 leading-relaxed">
                  5 specialized built-in agents (Planner, Researcher, Analyst, Reviewer, Synthesizer) with Pydantic JSON contracts.
                </p>
              </CardContent>
            </Card>

            {/* Gemini Model Provider */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-zinc-400" />
                  <CardTitle className="text-sm">Gemini Provider</CardTitle>
                </div>
                <Badge
                  variant={
                    health.components?.model_provider?.status === "healthy"
                      ? "success"
                      : "neutral"
                  }
                  dot
                >
                  {health.components?.model_provider?.status?.toUpperCase() || "CONFIGURED"}
                </Badge>
              </CardHeader>
              <CardContent className="pt-1 text-xs">
                <p className="text-zinc-400 leading-relaxed">
                  Model invocation runtime with structured outputs, exponential backoff retries, and bounded revision loops.
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Raw Diagnostic Payload */}
          <div className="flex flex-col gap-2">
            <h3 className="text-xs font-semibold text-zinc-300">
              Raw Health Telemetry Envelope (/api/v1/health)
            </h3>
            <CodeBlock code={health} language="json" maxHeight="max-h-64" />
          </div>
        </div>
      ) : null}
    </div>
  );
}
