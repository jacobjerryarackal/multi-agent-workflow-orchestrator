"use client";

import React, { useState } from "react";
import { TaskExecutionSummaryResponse } from "@/lib/types/api";
import { approveTask, rejectTask } from "@/lib/api/executions";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { ShieldCheck, Check, X, AlertTriangle } from "lucide-react";

export interface ApprovalGateCardProps {
  executionId: string;
  task: TaskExecutionSummaryResponse;
  onActionComplete?: () => void;
}

export function ApprovalGateCard({
  executionId,
  task,
  onActionComplete,
}: ApprovalGateCardProps) {
  const [approverName, setApproverName] = useState("lead_operator");
  const [comment, setComment] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [isRejectMode, setIsRejectMode] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApprove = async () => {
    setError(null);
    setIsSubmitting(true);
    try {
      await approveTask(executionId, task.task_key, {
        approver: approverName.trim() || "operator",
        comment: comment.trim() || undefined,
      });
      onActionComplete?.();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to approve task.");
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      setError("Rejection reason is required.");
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      await rejectTask(executionId, task.task_key, {
        rejector: approverName.trim() || "operator",
        reason: rejectReason.trim(),
      });
      onActionComplete?.();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to reject task.");
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="border-amber-800/80 bg-amber-950/20">
      <CardHeader className="border-amber-800/50 bg-amber-950/30 flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-amber-400" />
          <CardTitle className="text-amber-200">
            Action Required: Human Approval Gate
          </CardTitle>
        </div>
        <Badge variant="warning" dot>
          WAITING APPROVAL
        </Badge>
      </CardHeader>

      <CardContent className="flex flex-col gap-4 pt-4">
        <div>
          <span className="text-xs text-zinc-300">
            Task <strong className="text-zinc-100 font-mono-data">{task.task_key}</strong> (agent:{" "}
            <strong className="text-zinc-100 font-mono-data">{task.agent_id}</strong>) completed execution and is paused awaiting operational approval.
          </span>
        </div>

        {error ? (
          <div className="p-3 rounded bg-rose-950/70 border border-rose-800 text-xs text-rose-200 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        {/* Task Output Data Preview */}
        {Object.keys(task.output_data).length > 0 ? (
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-zinc-300">
              Task Output Payload for Review:
            </span>
            <CodeBlock code={task.output_data} maxHeight="max-h-48" />
          </div>
        ) : null}

        {/* Evaluation History if present */}
        {task.evaluation_history && task.evaluation_history.length > 0 ? (
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-zinc-300">
              Evaluation History & Quality Scores:
            </span>
            <CodeBlock code={task.evaluation_history} maxHeight="max-h-36" />
          </div>
        ) : null}

        {/* Inputs */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-amber-900/40">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-zinc-300">
              Operator / Approver Identity
            </label>
            <input
              type="text"
              value={approverName}
              onChange={(e) => setApproverName(e.target.value)}
              className="h-8 px-3 text-xs bg-zinc-900 border border-zinc-800 rounded text-zinc-100 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>

          {!isRejectMode ? (
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-zinc-300">
                Approval Comment (Optional)
              </label>
              <input
                type="text"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="e.g. Verified plan quality and approved next stage"
                className="h-8 px-3 text-xs bg-zinc-900 border border-zinc-800 rounded text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-amber-500"
              />
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-rose-300">
                Rejection Reason (Required) *
              </label>
              <input
                type="text"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="e.g. Findings failed verification criteria"
                className="h-8 px-3 text-xs bg-zinc-900 border border-rose-800 rounded text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-rose-500"
              />
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-3 border-t border-amber-900/40">
          <button
            type="button"
            onClick={() => setIsRejectMode(!isRejectMode)}
            className="text-xs text-zinc-400 hover:text-zinc-200 underline"
          >
            {isRejectMode ? "Switch to Approval" : "Switch to Rejection"}
          </button>

          <div className="flex items-center gap-2">
            {!isRejectMode ? (
              <Button
                variant="primary"
                size="sm"
                onClick={handleApprove}
                isLoading={isSubmitting}
                className="bg-emerald-500 text-black hover:bg-emerald-400 border-emerald-400"
              >
                <Check className="w-3.5 h-3.5" />
                Approve Task
              </Button>
            ) : (
              <Button
                variant="danger"
                size="sm"
                onClick={handleReject}
                isLoading={isSubmitting}
              >
                <X className="w-3.5 h-3.5" />
                Reject Task (Route to Escalated)
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
