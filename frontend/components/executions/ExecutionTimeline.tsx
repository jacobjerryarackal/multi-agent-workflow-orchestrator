"use client";

import React, { useState } from "react";
import { TaskExecutionSummaryResponse } from "@/lib/types/api";
import { Badge } from "@/components/ui/Badge";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { TASK_STATUS_CONFIG } from "@/lib/types/status";
import { formatDate, formatDuration } from "@/lib/utils/formatting";
import {
  CheckCircle2,
  XCircle,
  Clock,
  RotateCcw,
  Bot,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Cpu,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";

export interface ExecutionTimelineProps {
  tasks: TaskExecutionSummaryResponse[];
  selectedTaskKey?: string | null;
  onSelectTask?: (taskKey: string) => void;
}

export function ExecutionTimeline({
  tasks,
  selectedTaskKey,
  onSelectTask,
}: ExecutionTimelineProps) {
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(
    new Set(tasks.map((t) => t.task_key))
  );

  const toggleExpand = (key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-3">
      {tasks.map((task, idx) => {
        const isExpanded = expandedKeys.has(task.task_key);
        const statusCfg = TASK_STATUS_CONFIG[task.status] || {
          label: task.status,
          variant: "neutral",
        };
        const hasError = task.error_details != null && Object.keys(task.error_details).length > 0;
        const hasOutput = Object.keys(task.output_data).length > 0;
        const hasInputs = Object.keys(task.input_data).length > 0;
        const hasEval = task.evaluation_history && task.evaluation_history.length > 0;

        return (
          <div
            key={task.task_key}
            className={cn(
              "rounded-lg border bg-zinc-900/40 text-zinc-200 transition-all",
              selectedTaskKey === task.task_key
                ? "border-zinc-500 ring-1 ring-zinc-500 bg-zinc-900/80"
                : "border-zinc-800/80 hover:border-zinc-700"
            )}
          >
            {/* Timeline Header Row */}
            <div
              onClick={() => {
                onSelectTask?.(task.task_key);
                toggleExpand(task.task_key);
              }}
              className="p-3.5 flex items-center justify-between gap-3 cursor-pointer select-none"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-xs font-mono-data text-zinc-500 shrink-0">
                  0{idx + 1}
                </span>

                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-xs font-semibold text-zinc-100 truncate">
                    {task.task_key}
                  </span>
                  <div className="flex items-center gap-1 text-[11px] font-mono-data text-zinc-400">
                    <Bot className="w-3 h-3 text-zinc-500" />
                    <span>{task.agent_id}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                {task.attempt_count > 1 ? (
                  <span className="text-[11px] font-mono-data text-zinc-400">
                    att: {task.attempt_count}
                  </span>
                ) : null}

                {task.revision_count > 0 ? (
                  <span className="text-[11px] font-mono-data text-blue-300 flex items-center gap-0.5">
                    <RotateCcw className="w-2.5 h-2.5" />
                    rev: {task.revision_count}
                  </span>
                ) : null}

                <span className="text-[11px] font-mono-data text-zinc-400">
                  {formatDuration(task.execution_duration_ms)}
                </span>

                <Badge variant={statusCfg.variant} size="sm" dot>
                  {statusCfg.label}
                </Badge>

                {isExpanded ? (
                  <ChevronUp className="w-4 h-4 text-zinc-500" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-zinc-500" />
                )}
              </div>
            </div>

            {/* Expanded Details Body */}
            {isExpanded ? (
              <div className="px-4 pb-4 pt-1 border-t border-zinc-800/60 flex flex-col gap-3 text-xs">
                {/* Duration & Token metrics */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-[11px] font-mono-data text-zinc-400">
                  <div>
                    <span className="text-zinc-500 block">Started:</span>
                    <span className="text-zinc-300">
                      {formatDate(task.started_at, { includeTime: true })}
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block">Completed:</span>
                    <span className="text-zinc-300">
                      {formatDate(task.completed_at, { includeTime: true })}
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block">Attempts / Revisions:</span>
                    <span className="text-zinc-300">
                      {task.attempt_count} / {task.revision_count}
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block">Tokens:</span>
                    <span className="text-zinc-300">
                      {task.token_usage?.total_tokens ?? 0}
                    </span>
                  </div>
                </div>

                {/* Error Breakdown if any */}
                {hasError ? (
                  <div className="rounded border border-rose-900/80 bg-rose-950/30 p-3 text-rose-200 flex flex-col gap-1">
                    <span className="font-semibold text-xs flex items-center gap-1.5 text-rose-300">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      Execution Error Details
                    </span>
                    <CodeBlock
                      code={task.error_details!}
                      language="json"
                      maxHeight="max-h-36"
                    />
                  </div>
                ) : null}

                {/* Inputs & Outputs tabs/blocks */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 pt-2">
                  {hasInputs ? (
                    <div className="flex flex-col gap-1">
                      <span className="text-[11px] font-mono-data text-zinc-400">
                        Input Payload
                      </span>
                      <CodeBlock
                        code={task.input_data}
                        language="json"
                        maxHeight="max-h-48"
                      />
                    </div>
                  ) : null}

                  {hasOutput ? (
                    <div className="flex flex-col gap-1">
                      <span className="text-[11px] font-mono-data text-zinc-400">
                        Output Payload
                      </span>
                      <CodeBlock
                        code={task.output_data}
                        language="json"
                        maxHeight="max-h-48"
                      />
                    </div>
                  ) : null}
                </div>

                {/* Evaluation History */}
                {hasEval ? (
                  <div className="flex flex-col gap-1 pt-2 border-t border-zinc-800/60">
                    <span className="text-[11px] font-mono-data text-zinc-400 flex items-center gap-1">
                      <RotateCcw className="w-3 h-3 text-blue-400" />
                      Quality Gate Evaluation Iterations
                    </span>
                    <CodeBlock
                      code={task.evaluation_history}
                      language="json"
                      maxHeight="max-h-36"
                    />
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
