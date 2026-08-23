"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getWorkflow } from "@/lib/api/workflows";
import { getExecutions } from "@/lib/api/executions";
import {
  WorkflowResponse,
  WorkflowExecutionSummaryResponse,
} from "@/lib/types/api";
import { WorkflowDAGView } from "@/components/workflows/WorkflowDAGView";
import { TriggerExecutionModal } from "@/components/workflows/TriggerExecutionModal";
import { ExecutionTable } from "@/components/executions/ExecutionTable";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { LoadingState, ErrorState } from "@/components/ui/LoadingState";
import { formatDate } from "@/lib/utils/formatting";
import {
  ArrowLeft,
  GitFork,
  Play,
  Clock,
  Layers,
  FileJson,
  ShieldCheck,
  RotateCcw,
} from "lucide-react";

export default function WorkflowDetailPage() {
  const params = useParams();
  const workflowId = params?.id as string;

  const [workflow, setWorkflow] = useState<WorkflowResponse | null>(null);
  const [executions, setExecutions] = useState<WorkflowExecutionSummaryResponse[]>([]);
  const [selectedTaskKey, setSelectedTaskKey] = useState<string | null>(null);
  const [isTriggerModalOpen, setIsTriggerModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"dag" | "json">("dag");

  const loadWorkflowData = async () => {
    if (!workflowId) return;
    setIsLoading(true);
    setError(null);
    try {
      const [wf, execs] = await Promise.all([
        getWorkflow(workflowId),
        getExecutions({ workflow_id: workflowId, limit: 10 }),
      ]);
      setWorkflow(wf);
      setExecutions(execs.items);
      if (wf.tasks.length > 0) {
        setSelectedTaskKey(wf.tasks[0].task_key);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load workflow.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadWorkflowData();
  }, [workflowId]);

  if (isLoading) {
    return <LoadingState message="Loading workflow specification..." />;
  }

  if (error || !workflow) {
    return (
      <ErrorState
        title="Workflow Not Found"
        error={error || "Specification could not be located."}
        onRetry={loadWorkflowData}
      />
    );
  }

  const selectedTask = workflow.tasks.find((t) => t.task_key === selectedTaskKey);

  return (
    <div className="flex flex-col gap-6">
      {/* Navigation and Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <Link href="/workflows">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-zinc-100 tracking-tight">
                {workflow.name}
              </h1>
              <Badge variant="neutral">v{workflow.version}</Badge>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5 max-w-2xl">
              {workflow.description}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsTriggerModalOpen(true)}
          >
            <Play className="w-3.5 h-3.5 text-emerald-400" />
            Trigger Execution
          </Button>
        </div>
      </div>

      {/* Metadata summary bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-3">
          <span className="text-[11px] font-mono-data text-zinc-500 uppercase block">
            DAG NODES
          </span>
          <span className="text-sm font-semibold text-zinc-100">
            {workflow.tasks.length} tasks
          </span>
        </Card>

        <Card className="p-3">
          <span className="text-[11px] font-mono-data text-zinc-500 uppercase block">
            MAX DURATION
          </span>
          <span className="text-sm font-semibold text-zinc-100">
            {workflow.max_workflow_duration_seconds}s
          </span>
        </Card>

        <Card className="p-3">
          <span className="text-[11px] font-mono-data text-zinc-500 uppercase block">
            PARALLEL LIMIT
          </span>
          <span className="text-sm font-semibold text-zinc-100">
            {workflow.max_parallel_tasks} workers
          </span>
        </Card>

        <Card className="p-3">
          <span className="text-[11px] font-mono-data text-zinc-500 uppercase block">
            CREATED
          </span>
          <span className="text-sm font-semibold text-zinc-100">
            {formatDate(workflow.created_at, { relative: true })}
          </span>
        </Card>
      </div>

      {/* View Switcher: DAG vs RAW JSON */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setActiveTab("dag")}
          className={`px-3 py-1 text-xs font-medium rounded border transition-colors ${
            activeTab === "dag"
              ? "bg-zinc-100 text-zinc-900 border-white font-semibold"
              : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200"
          }`}
        >
          DAG Topology Graph
        </button>
        <button
          onClick={() => setActiveTab("json")}
          className={`px-3 py-1 text-xs font-medium rounded border transition-colors ${
            activeTab === "json"
              ? "bg-zinc-100 text-zinc-900 border-white font-semibold"
              : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200"
          }`}
        >
          Raw Specification JSON
        </button>
      </div>

      {activeTab === "dag" ? (
        <div className="flex flex-col gap-4">
          <WorkflowDAGView
            tasks={workflow.tasks}
            selectedTaskKey={selectedTaskKey}
            onSelectTask={(k) => setSelectedTaskKey(k)}
          />

          {/* Selected Task Inspector Panel */}
          {selectedTask ? (
            <Card className="border-zinc-800 bg-zinc-900/40">
              <CardHeader className="py-2.5 flex flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-zinc-100">
                    Selected Node Spec: {selectedTask.name}
                  </span>
                  <Badge variant="neutral">{selectedTask.task_key}</Badge>
                </div>
                <span className="text-[11px] font-mono-data text-zinc-400">
                  Agent: <strong className="text-zinc-200">{selectedTask.agent_id}</strong>
                </span>
              </CardHeader>
              <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-3 text-xs">
                <div>
                  <span className="text-[11px] font-mono-data text-zinc-500 uppercase block mb-1">
                    Prerequisites
                  </span>
                  <span className="text-zinc-300">
                    {selectedTask.depends_on.length > 0
                      ? selectedTask.depends_on.join(", ")
                      : "None (Root Entrypoint)"}
                  </span>
                </div>

                <div>
                  <span className="text-[11px] font-mono-data text-zinc-500 uppercase block mb-1">
                    Retry Policy
                  </span>
                  <span className="text-zinc-300 font-mono-data text-[11px]">
                    Max {selectedTask.retry_policy?.max_attempts ?? 3} attempts
                    ({selectedTask.retry_policy?.backoff_multiplier ?? 2}x backoff)
                  </span>
                </div>

                <div>
                  <span className="text-[11px] font-mono-data text-zinc-500 uppercase block mb-1">
                    Gates
                  </span>
                  <div className="flex items-center gap-2">
                    {selectedTask.approval_gate?.required ? (
                      <Badge variant="warning" size="sm">
                        Approval Required
                      </Badge>
                    ) : null}
                    {selectedTask.evaluation_gate?.enabled ? (
                      <Badge variant="info" size="sm">
                        Eval Active (min score:{" "}
                        {selectedTask.evaluation_gate.min_pass_score})
                      </Badge>
                    ) : null}
                    {!selectedTask.approval_gate?.required &&
                    !selectedTask.evaluation_gate?.enabled ? (
                      <span className="text-zinc-500 text-xs">Direct Execution</span>
                    ) : null}
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : (
        <CodeBlock code={workflow} language="json" maxHeight="max-h-[500px]" />
      )}

      {/* Execution History */}
      <div className="flex flex-col gap-3 pt-4 border-t border-zinc-800">
        <h2 className="text-sm font-semibold text-zinc-100">
          Execution Runs for this Workflow
        </h2>
        <ExecutionTable
          executions={executions}
          workflowNameMap={{ [workflow.id]: workflow.name }}
        />
      </div>

      <TriggerExecutionModal
        workflow={workflow}
        isOpen={isTriggerModalOpen}
        onClose={() => setIsTriggerModalOpen(false)}
      />
    </div>
  );
}
