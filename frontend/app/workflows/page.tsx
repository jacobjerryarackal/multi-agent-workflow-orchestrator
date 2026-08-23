"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getWorkflows } from "@/lib/api/workflows";
import { WorkflowResponse } from "@/lib/types/api";
import { WorkflowTable } from "@/components/workflows/WorkflowTable";
import { TriggerExecutionModal } from "@/components/workflows/TriggerExecutionModal";
import { LoadingState, ErrorState } from "@/components/ui/LoadingState";
import { Button } from "@/components/ui/Button";
import { Plus, RefreshCw, GitFork } from "lucide-react";

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowResponse | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getWorkflows();
      setWorkflows(res.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load workflows.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTrigger = (workflow: WorkflowResponse) => {
    setSelectedWorkflow(workflow);
    setIsModalOpen(true);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
            <GitFork className="w-5 h-5 text-zinc-300" />
            Workflow Specifications
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Registered multi-agent Directed Acyclic Graphs (DAGs) and task definitions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={loadData} isLoading={isLoading}>
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
          <Link href="/workflows/new">
            <Button variant="primary" size="sm">
              <Plus className="w-3.5 h-3.5" />
              New Workflow
            </Button>
          </Link>
        </div>
      </div>

      {isLoading ? (
        <LoadingState message="Loading registered workflows..." />
      ) : error ? (
        <ErrorState title="Workflows Query Error" error={error} onRetry={loadData} />
      ) : (
        <WorkflowTable
          workflows={workflows}
          onTriggerExecution={handleTrigger}
        />
      )}

      <TriggerExecutionModal
        workflow={selectedWorkflow}
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setSelectedWorkflow(null);
        }}
      />
    </div>
  );
}
