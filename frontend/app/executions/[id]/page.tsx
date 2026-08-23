"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getExecution, cancelExecution } from "@/lib/api/executions";
import { getWorkflow } from "@/lib/api/workflows";
import { getExecutionEvents } from "@/lib/api/events";
import { getExecutionArtifacts } from "@/lib/api/artifacts";
import {
  WorkflowExecutionDetailResponse,
  WorkflowResponse,
  EventResponse,
  ArtifactResponse,
  TaskExecutionSummaryResponse,
} from "@/lib/types/api";
import { WorkflowDAGView } from "@/components/workflows/WorkflowDAGView";
import { ExecutionTimeline } from "@/components/executions/ExecutionTimeline";
import { ApprovalGateCard } from "@/components/executions/ApprovalGateCard";
import { EventAuditStream } from "@/components/events/EventAuditStream";
import { ArtifactList } from "@/components/artifacts/ArtifactList";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { LoadingState, ErrorState } from "@/components/ui/LoadingState";
import { WORKFLOW_STATUS_CONFIG } from "@/lib/types/status";
import { formatDate, formatDuration, formatShortId } from "@/lib/utils/formatting";
import {
  ArrowLeft,
  PlayCircle,
  Clock,
  CheckCircle2,
  AlertTriangle,
  StopCircle,
  RotateCcw,
  RefreshCw,
  FileText,
  Activity,
  Layers,
} from "lucide-react";

export default function ExecutionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const executionId = params?.id as string;

  const [execution, setExecution] = useState<WorkflowExecutionDetailResponse | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowResponse | null>(null);
  const [events, setEvents] = useState<EventResponse[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactResponse[]>([]);
  const [selectedTaskKey, setSelectedTaskKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCancelling, setIsCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"timeline" | "dag" | "events" | "artifacts" | "io">("timeline");

  const loadExecutionData = async () => {
    if (!executionId) return;
    try {
      const exec = await getExecution(executionId);
      setExecution(exec);

      const [wf, evtRes, artRes] = await Promise.all([
        getWorkflow(exec.workflow_id).catch(() => null),
        getExecutionEvents(executionId).catch(() => ({ items: [], total_count: 0 })),
        getExecutionArtifacts(executionId).catch(() => ({ items: [], total_count: 0 })),
      ]);

      setWorkflow(wf);
      setEvents(evtRes.items);
      setArtifacts(artRes.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load execution.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadExecutionData();
    const interval = setInterval(() => {
      // Auto-poll if execution is active
      if (execution?.status === "RUNNING" || execution?.status === "QUEUED" || execution?.status === "PAUSED") {
        loadExecutionData();
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [executionId, execution?.status]);

  const handleCancel = async () => {
    if (!confirm("Are you sure you want to cancel this active execution run?")) return;
    setIsCancelling(true);
    try {
      await cancelExecution(executionId);
      await loadExecutionData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to cancel execution.");
    } finally {
      setIsCancelling(false);
    }
  };

  if (isLoading && !execution) {
    return <LoadingState message="Loading execution state and task progression..." />;
  }

  if (error && !execution) {
    return (
      <ErrorState
        title="Execution Load Error"
        error={error}
        onRetry={loadExecutionData}
      />
    );
  }

  if (!execution) return null;

  const statusCfg = WORKFLOW_STATUS_CONFIG[execution.status] || {
    label: execution.status,
    variant: "neutral",
  };

  const runtimeTaskMap = execution.tasks.reduce<Record<string, TaskExecutionSummaryResponse>>(
    (acc, t) => {
      acc[t.task_key] = t;
      return acc;
    },
    {}
  );

  // Check for tasks waiting for approval
  const waitingApprovalTask = execution.tasks.find(
    (t) => t.status === "WAITING_APPROVAL"
  );

  return (
    <div className="flex flex-col gap-6">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <Link href="/executions">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
                <PlayCircle className="w-5 h-5 text-zinc-300" />
                Execution {formatShortId(execution.id, 8)}
              </h1>
              <Badge variant={statusCfg.variant} size="md" dot>
                {statusCfg.label}
              </Badge>
            </div>
            <div className="flex items-center gap-2 text-xs text-zinc-400 mt-0.5 font-mono-data">
              <span>Workflow:</span>
              <Link
                href={`/workflows/${execution.workflow_id}`}
                className="text-zinc-200 hover:text-white hover:underline"
              >
                {workflow?.name || execution.workflow_id}
              </Link>
              {execution.idempotency_key ? (
                <>
                  <span className="text-zinc-600">·</span>
                  <span>idem: {execution.idempotency_key}</span>
                </>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={loadExecutionData}>
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>

          {execution.status === "RUNNING" || execution.status === "PAUSED" ? (
            <Button
              variant="danger"
              size="sm"
              onClick={handleCancel}
              isLoading={isCancelling}
            >
              <StopCircle className="w-3.5 h-3.5" />
              Cancel Execution
            </Button>
          ) : null}
        </div>
      </div>

      {/* Prominent Approval Action Card if waiting for human operator */}
      {waitingApprovalTask ? (
        <ApprovalGateCard
          executionId={execution.id}
          task={waitingApprovalTask}
          onActionComplete={loadExecutionData}
        />
      ) : null}

      {/* Execution Stats Metric Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-3">
          <span className="text-[11px] font-mono-data text-zinc-500 uppercase block">
            DURATION
          </span>
          <span className="text-sm font-semibold text-zinc-100 font-mono-data">
            {formatDuration(execution.execution_duration_ms)}
          </span>
        </Card>

        <Card className="p-3">
          <span className="text-[11px] font-mono-data text-zinc-500 uppercase block">
            STARTED
          </span>
          <span className="text-sm font-semibold text-zinc-100 font-mono-data">
            {formatDate(execution.started_at || execution.created_at, {
              includeTime: true,
            })}
          </span>
        </Card>

        <Card className="p-3">
          <span className="text-[11px] font-mono-data text-zinc-500 uppercase block">
            TASKS PROGRESSION
          </span>
          <span className="text-sm font-semibold text-zinc-100 font-mono-data">
            {execution.tasks.filter((t) => t.status === "COMPLETED").length} /{" "}
            {execution.tasks.length} Completed
          </span>
        </Card>

        <Card className="p-3">
          <span className="text-[11px] font-mono-data text-zinc-500 uppercase block">
            ARTIFACTS
          </span>
          <span className="text-sm font-semibold text-zinc-100 font-mono-data">
            {artifacts.length} Produced
          </span>
        </Card>
      </div>

      {/* Error Summary Banner if execution failed */}
      {execution.error_summary ? (
        <div className="p-4 rounded-lg border border-rose-900 bg-rose-950/30 text-rose-200 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex flex-col gap-1">
            <span className="text-xs font-semibold text-rose-300">
              Workflow Execution Terminated with Failure
            </span>
            <p className="text-xs text-rose-300/80 leading-relaxed font-mono-data">
              {execution.error_summary}
            </p>
          </div>
        </div>
      ) : null}

      {/* Tabs navigation */}
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
        <button
          onClick={() => setActiveTab("timeline")}
          className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
            activeTab === "timeline"
              ? "bg-zinc-100 text-zinc-900 font-semibold"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Task Progression Timeline ({execution.tasks.length})
        </button>

        {workflow ? (
          <button
            onClick={() => setActiveTab("dag")}
            className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
              activeTab === "dag"
                ? "bg-zinc-100 text-zinc-900 font-semibold"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Live DAG State
          </button>
        ) : null}

        <button
          onClick={() => setActiveTab("artifacts")}
          className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
            activeTab === "artifacts"
              ? "bg-zinc-100 text-zinc-900 font-semibold"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Artifacts & Verification ({artifacts.length})
        </button>

        <button
          onClick={() => setActiveTab("events")}
          className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
            activeTab === "events"
              ? "bg-zinc-100 text-zinc-900 font-semibold"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Audit Telemetry Events ({events.length})
        </button>

        <button
          onClick={() => setActiveTab("io")}
          className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
            activeTab === "io"
              ? "bg-zinc-100 text-zinc-900 font-semibold"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Inputs & Final Outputs
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === "timeline" ? (
        <ExecutionTimeline
          tasks={execution.tasks}
          selectedTaskKey={selectedTaskKey}
          onSelectTask={(k) => setSelectedTaskKey(k)}
        />
      ) : activeTab === "dag" && workflow ? (
        <WorkflowDAGView
          tasks={workflow.tasks}
          runtimeTasks={runtimeTaskMap}
          selectedTaskKey={selectedTaskKey}
          onSelectTask={(k) => setSelectedTaskKey(k)}
        />
      ) : activeTab === "artifacts" ? (
        <ArtifactList executionId={execution.id} artifacts={artifacts} />
      ) : activeTab === "events" ? (
        <EventAuditStream events={events} />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold text-zinc-300">
              Initial Execution Inputs
            </span>
            <CodeBlock
              code={execution.initial_inputs}
              language="json"
              maxHeight="max-h-96"
            />
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold text-zinc-300">
              Final Synthesized Outputs
            </span>
            <CodeBlock
              code={execution.final_outputs}
              language="json"
              maxHeight="max-h-96"
            />
          </div>
        </div>
      )}
    </div>
  );
}
