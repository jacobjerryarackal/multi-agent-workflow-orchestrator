"use client";

import React, { useEffect, useState } from "react";
import { getSystemHealth, getSystemTelemetry } from "@/lib/api/health";
import { HealthResponse, TelemetrySnapshotResponse } from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { LoadingState, ErrorState } from "@/components/ui/LoadingState";
import { formatDate } from "@/lib/utils/formatting";
import { Server, Database, Cpu, RefreshCw, Activity, Terminal, BarChart2, Layers, CheckCircle, AlertTriangle } from "lucide-react";

export default function SystemHealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetrySnapshotResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [healthData, telemetryData] = await Promise.all([
        getSystemHealth(),
        getSystemTelemetry().catch(() => null),
      ]);
      setHealth(healthData);
      setTelemetry(telemetryData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to query system health endpoint.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Compute summary stats from telemetry counters
  const getCounterSum = (name: string): number => {
    if (!telemetry?.counters || !telemetry.counters[name]) return 0;
    return telemetry.counters[name].reduce((acc, item) => acc + (item.value || 0), 0);
  };

  const getGaugeVal = (name: string): number => {
    if (!telemetry?.gauges || !telemetry.gauges[name] || telemetry.gauges[name].length === 0) return 0;
    return telemetry.gauges[name][0].value || 0;
  };

  const httpRequestsTotal = getCounterSum("http_requests_total");
  const workflowsStarted = getCounterSum("workflow_started_total");
  const workflowsCompleted = getCounterSum("workflow_completed_total");
  const tasksCompleted = getCounterSum("task_completed_total");
  const modelTokensTotal = getCounterSum("model_tokens_total");
  const activeDbConnections = getGaugeVal("database_connections_checked_out");
  const backgroundActive = getGaugeVal("background_active_executions");

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
            <Server className="w-5 h-5 text-zinc-300" />
            System Health & Telemetry
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Operational status of PostgreSQL persistence, Gemini LLM provider, agent registry, and telemetry metrics.
          </p>
        </div>

        <Button variant="secondary" size="sm" onClick={loadData} isLoading={isLoading}>
          <RefreshCw className="w-3.5 h-3.5" />
          Poll System
        </Button>
      </div>

      {isLoading && !health ? (
        <LoadingState message="Polling cluster health telemetry..." />
      ) : error && !health ? (
        <ErrorState title="Telemetry Unreachable" error={error} onRetry={loadData} />
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

          {/* Real-time Telemetry Metrics KPI Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 bg-zinc-900/80 border border-zinc-800 rounded-lg">
              <div className="text-xs text-zinc-400 flex items-center gap-1.5 font-mono-data">
                <BarChart2 className="w-3.5 h-3.5 text-indigo-400" />
                HTTP Requests
              </div>
              <div className="text-xl font-bold text-zinc-100 mt-1 font-mono-data">
                {httpRequestsTotal}
              </div>
            </div>

            <div className="p-3 bg-zinc-900/80 border border-zinc-800 rounded-lg">
              <div className="text-xs text-zinc-400 flex items-center gap-1.5 font-mono-data">
                <Layers className="w-3.5 h-3.5 text-blue-400" />
                Workflows (Done/Run)
              </div>
              <div className="text-xl font-bold text-zinc-100 mt-1 font-mono-data">
                {workflowsCompleted} / {workflowsStarted}
              </div>
            </div>

            <div className="p-3 bg-zinc-900/80 border border-zinc-800 rounded-lg">
              <div className="text-xs text-zinc-400 flex items-center gap-1.5 font-mono-data">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                Tasks Completed
              </div>
              <div className="text-xl font-bold text-zinc-100 mt-1 font-mono-data">
                {tasksCompleted}
              </div>
            </div>

            <div className="p-3 bg-zinc-900/80 border border-zinc-800 rounded-lg">
              <div className="text-xs text-zinc-400 flex items-center gap-1.5 font-mono-data">
                <Database className="w-3.5 h-3.5 text-amber-400" />
                DB Checked Out / BG
              </div>
              <div className="text-xl font-bold text-zinc-100 mt-1 font-mono-data">
                {activeDbConnections} / {backgroundActive}
              </div>
            </div>
          </div>

          {/* Component breakdowns */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
                  ACID state persistence with async connection pooling and SELECT FOR UPDATE leases.
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
                  5 specialized built-in agents (Planner, Researcher, Analyst, Reviewer, Synthesizer).
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
                  Token metrics: {modelTokensTotal} tokens processed across workflows.
                </p>
              </CardContent>
            </Card>

            {/* Background Manager */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-zinc-400" />
                  <CardTitle className="text-sm">Background Worker</CardTitle>
                </div>
                <Badge
                  variant={
                    health.components?.background_manager?.status === "healthy"
                      ? "success"
                      : "neutral"
                  }
                  dot
                >
                  {health.components?.background_manager?.status?.toUpperCase() || "ACTIVE"}
                </Badge>
              </CardHeader>
              <CardContent className="pt-1 text-xs">
                <p className="text-zinc-400 leading-relaxed">
                  Active background executions: {backgroundActive}. Watchdog supervisor running.
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Raw Diagnostic Payload */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-semibold text-zinc-300">
                Health Check Diagnostics (/api/v1/health)
              </h3>
              <CodeBlock code={health} language="json" maxHeight="max-h-64" />
            </div>

            {telemetry && (
              <div className="flex flex-col gap-2">
                <h3 className="text-xs font-semibold text-zinc-300">
                  Telemetry Metrics Snapshot (/api/v1/telemetry)
                </h3>
                <CodeBlock code={telemetry} language="json" maxHeight="max-h-64" />
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

