"use client";

import React, { useState } from "react";
import { WorkflowResponse } from "@/lib/types/api";
import { submitWorkflowExecution } from "@/lib/api/executions";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { useRouter } from "next/navigation";
import { Play, AlertCircle } from "lucide-react";

export interface TriggerExecutionModalProps {
  workflow: WorkflowResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

export function TriggerExecutionModal({
  workflow,
  isOpen,
  onClose,
}: TriggerExecutionModalProps) {
  const router = useRouter();
  const [inputJson, setInputJson] = useState('{\n  "objective": "Research and analyze system requirements"\n}');
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!workflow) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    let parsedInput: Record<string, unknown> = {};
    if (inputJson.trim()) {
      try {
        parsedInput = JSON.parse(inputJson);
      } catch (err) {
        setError("Invalid JSON format in input parameters.");
        return;
      }
    }

    setIsSubmitting(true);
    try {
      const result = await submitWorkflowExecution(workflow.id, {
        input_data: parsedInput,
        idempotency_key: idempotencyKey.trim() || undefined,
        trigger_type: "manual",
      });
      onClose();
      router.push(`/executions/${result.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to submit execution.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Run Workflow: ${workflow.name}`}
      description={`Submits a new execution instance for workflow specification v${workflow.version}.`}
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error ? (
          <div className="p-3 rounded bg-rose-950/60 border border-rose-800 text-xs text-rose-200 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        ) : null}

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-zinc-300">
            Execution Input Parameters (JSON)
          </label>
          <textarea
            value={inputJson}
            onChange={(e) => setInputJson(e.target.value)}
            rows={7}
            className="w-full p-3 font-mono-data text-xs bg-black/60 border border-zinc-800 rounded text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-400"
            placeholder='{\n  "query": "Your input data"\n}'
          />
          <span className="text-[11px] text-zinc-500">
            Passed as initial inputs into the root DAG nodes of this workflow.
          </span>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-zinc-300">
            Client Idempotency Key (Optional)
          </label>
          <input
            type="text"
            value={idempotencyKey}
            onChange={(e) => setIdempotencyKey(e.target.value)}
            placeholder="e.g. exec-batch-2026-08-23-001"
            className="w-full h-8 px-3 text-xs font-mono-data bg-black/60 border border-zinc-800 rounded text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-400"
          />
          <span className="text-[11px] text-zinc-500">
            Guarantees idempotent deduplication. Re-submitting with same key returns existing execution.
          </span>
        </div>

        <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-800">
          <Button variant="ghost" size="sm" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            type="submit"
            isLoading={isSubmitting}
          >
            <Play className="w-3.5 h-3.5" />
            Dispatch Execution
          </Button>
        </div>
      </form>
    </Modal>
  );
}
