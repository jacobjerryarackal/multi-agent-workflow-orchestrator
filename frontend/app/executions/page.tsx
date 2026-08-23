"use client";

import React, { useEffect, useState } from "react";
import { getExecutions } from "@/lib/api/executions";
import { getWorkflows } from "@/lib/api/workflows";
import {
  WorkflowExecutionSummaryResponse,
  WorkflowResponse,
} from "@/lib/types/api";
import { ExecutionTable } from "@/components/executions/ExecutionTable";
import { LoadingState, ErrorState } from "@/components/ui/LoadingState";
import { Button } from "@/components/ui/Button";
import { PlayCircle, RefreshCw } from "lucide-react";

export default function ExecutionsPage() {
  const [executions, setExecutions] = useState<WorkflowExecutionSummaryResponse[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [execRes, wfRes] = await Promise.all([
        getExecutions({ limit: 50 }),
        getWorkflows({ limit: 50 }),
      ]);
      setExecutions(execRes.items);
      setWorkflows(wfRes.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load executions.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 8000); // 8s auto-refresh for live execution updates
    return () => clearInterval(interval);
  }, []);

  const workflowNameMap = workflows.reduce<Record<string, string>>((acc, wf) => {
    acc[wf.id] = wf.name;
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
            <PlayCircle className="w-5 h-5 text-zinc-300" />
            Execution Operations
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Audit history, active runs, duration telemetry, and task status progression.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={loadData}
            isLoading={isLoading}
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      {isLoading && executions.length === 0 ? (
        <LoadingState message="Querying execution registry..." />
      ) : error && executions.length === 0 ? (
        <ErrorState title="Executions Query Error" error={error} onRetry={loadData} />
      ) : (
        <ExecutionTable
          executions={executions}
          workflowNameMap={workflowNameMap}
        />
      )}
    </div>
  );
}
