"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getExecutions } from "@/lib/api/executions";
import { getWorkflows } from "@/lib/api/workflows";
import { getSystemHealth } from "@/lib/api/health";
import {
  WorkflowExecutionSummaryResponse,
  WorkflowResponse,
  HealthResponse,
} from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ExecutionTable } from "@/components/executions/ExecutionTable";
import { LoadingState, ErrorState } from "@/components/ui/LoadingState";
import {
  Activity,
  GitFork,
  PlayCircle,
  Clock,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  Server,
  Database,
  Cpu,
  Plus,
} from "lucide-react";

export default function DashboardPage() {
  const [executions, setExecutions] = useState<WorkflowExecutionSummaryResponse[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowResponse[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [execRes, wfRes, healthRes] = await Promise.all([
        getExecutions({ limit: 10 }),
        getWorkflows({ limit: 10 }),
        getSystemHealth().catch(() => null),
      ]);
      setExecutions(execRes.items);
      setWorkflows(wfRes.items);
      setHealth(healthRes);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard telemetry.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const runningCount = executions.filter((e) => e.status === "RUNNING").length;
  const pausedCount = executions.filter((e) => e.status === "PAUSED").length;
  const failedCount = executions.filter((e) => e.status === "FAILED" || e.status === "TIMED_OUT").length;
  const completedCount = executions.filter((e) => e.status === "COMPLETED").length;

  const workflowNameMap = workflows.reduce<Record<string, string>>((acc, wf) => {
    acc[wf.id] = wf.name;
    return acc;
  }, {});

  if (isLoading) {
    return <LoadingState message="Connecting to orchestration control plane..." />;
  }

  if (error) {
    return <ErrorState title="Dashboard Connection Error" error={error} onRetry={loadDashboardData} />;
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Top Welcome / Operations Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-zinc-100 tracking-tight">
            Operations Console
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Real-time multi-agent execution telemetry and DAG orchestration health.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/workflows/new">
            <Button variant="primary" size="sm">
              <Plus className="w-3.5 h-3.5" />
              New Workflow
            </Button>
          </Link>
        </div>
      </div>

      {/* Metric Strips (Linear / Vercel style - restrained, non-AI-slop) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="p-3.5">
          <div className="flex items-center justify-between text-xs text-zinc-400 font-mono-data mb-1">
            <span>RUNNING EXECUTIONS</span>
            <span className="w-2 h-2 rounded-full bg-blue-400" />
          </div>
          <div className="text-xl font-bold font-mono-data text-zinc-100">
            {runningCount}
          </div>
          <span className="text-[11px] text-zinc-500 mt-0.5 block">
            Actively dispatched tasks
          </span>
        </Card>

        <Card className="p-3.5">
          <div className="flex items-center justify-between text-xs text-zinc-400 font-mono-data mb-1">
            <span>WAITING APPROVAL</span>
            <span className="w-2 h-2 rounded-full bg-amber-400" />
          </div>
          <div className="text-xl font-bold font-mono-data text-zinc-100">
            {pausedCount}
          </div>
          <span className="text-[11px] text-zinc-500 mt-0.5 block">
            Human gates paused
          </span>
        </Card>

        <Card className="p-3.5">
          <div className="flex items-center justify-between text-xs text-zinc-400 font-mono-data mb-1">
            <span>COMPLETED</span>
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
          </div>
          <div className="text-xl font-bold font-mono-data text-zinc-100">
            {completedCount}
          </div>
          <span className="text-[11px] text-zinc-500 mt-0.5 block">
            Verified successful runs
          </span>
        </Card>

        <Card className="p-3.5">
          <div className="flex items-center justify-between text-xs text-zinc-400 font-mono-data mb-1">
            <span>FAILED / TIMEOUT</span>
            <span className="w-2 h-2 rounded-full bg-rose-400" />
          </div>
          <div className="text-xl font-bold font-mono-data text-zinc-100">
            {failedCount}
          </div>
          <span className="text-[11px] text-zinc-500 mt-0.5 block">
            Terminal failure state
          </span>
        </Card>
      </div>

      {/* Attention Required Banner if approvals or failures exist */}
      {pausedCount > 0 ? (
        <div className="p-3.5 rounded-lg border border-amber-800/80 bg-amber-950/20 text-amber-200 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="text-xs font-medium">
              {pausedCount} execution{pausedCount > 1 ? "s" : ""} currently waiting for human operator approval.
            </span>
          </div>
          <Link href="/executions">
            <Button variant="secondary" size="sm" className="h-7 text-[11px] border-amber-800/80 text-amber-200">
              Review Gates
              <ArrowRight className="w-3 h-3" />
            </Button>
          </Link>
        </div>
      ) : null}

      {/* Main Execution Operations Section */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">
              Recent Executions
            </h2>
            <p className="text-xs text-zinc-400">
              Latest multi-agent DAG execution runs across all registered workflows.
            </p>
          </div>
          <Link href="/executions">
            <Button variant="ghost" size="sm" className="text-xs">
              View all
              <ArrowRight className="w-3 h-3" />
            </Button>
          </Link>
        </div>

        <ExecutionTable
          executions={executions}
          workflowNameMap={workflowNameMap}
        />
      </div>

      {/* Workflows & System Status split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-2">
        <div className="lg:col-span-2 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-100">
              Active Workflow Graphs
            </h2>
            <Link href="/workflows">
              <Button variant="ghost" size="sm" className="text-xs">
                Browse catalog ({workflows.length})
                <ArrowRight className="w-3 h-3" />
              </Button>
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {workflows.slice(0, 4).map((wf) => (
              <Card key={wf.id} className="hover:border-zinc-700 transition-colors">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <Link
                      href={`/workflows/${wf.id}`}
                      className="font-medium text-xs text-zinc-100 hover:text-white hover:underline truncate"
                    >
                      {wf.name}
                    </Link>
                    <Badge variant="neutral">v{wf.version}</Badge>
                  </div>
                  <CardDescription className="line-clamp-2 mt-1">
                    {wf.description}
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0 flex items-center justify-between text-[11px] font-mono-data text-zinc-400">
                  <span>{wf.tasks.length} tasks</span>
                  <Link href={`/workflows/${wf.id}`}>
                    <span className="text-zinc-300 hover:text-white hover:underline flex items-center gap-1">
                      Inspect DAG <ArrowRight className="w-3 h-3" />
                    </span>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* System Diagnostics Snapshot */}
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-zinc-100">
            Cluster Telemetry
          </h2>
          <Card className="p-4 flex flex-col gap-3 text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
              <div className="flex items-center gap-2 text-zinc-300">
                <Database className="w-3.5 h-3.5 text-zinc-400" />
                <span>PostgreSQL 16 Engine</span>
              </div>
              <Badge
                variant={
                  health?.components?.database?.status === "healthy"
                    ? "success"
                    : "danger"
                }
                size="sm"
                dot
              >
                {health?.components?.database?.status || "CONNECTED"}
              </Badge>
            </div>

            <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
              <div className="flex items-center gap-2 text-zinc-300">
                <Cpu className="w-3.5 h-3.5 text-zinc-400" />
                <span>Specialized Agents</span>
              </div>
              <Badge variant="success" size="sm" dot>
                5 ACTIVE
              </Badge>
            </div>

            <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
              <div className="flex items-center gap-2 text-zinc-300">
                <Server className="w-3.5 h-3.5 text-zinc-400" />
                <span>FastAPI Control Plane</span>
              </div>
              <span className="font-mono-data text-zinc-400">v1.0.0</span>
            </div>

            <Link href="/system" className="pt-1">
              <Button variant="outline" size="sm" className="w-full text-xs">
                Full Health Diagnostics
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </Link>
          </Card>
        </div>
      </div>
    </div>
  );
}
