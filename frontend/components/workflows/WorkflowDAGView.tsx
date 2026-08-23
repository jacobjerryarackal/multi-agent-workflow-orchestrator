"use client";

import React, { useMemo } from "react";
import { TaskSpecSchema, TaskExecutionSummaryResponse } from "@/lib/types/api";
import { Badge } from "@/components/ui/Badge";
import { TASK_STATUS_CONFIG } from "@/lib/types/status";
import { ArrowRight, Bot, ShieldCheck, CheckCircle2, Clock, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export interface WorkflowDAGViewProps {
  tasks: TaskSpecSchema[];
  runtimeTasks?: Record<string, TaskExecutionSummaryResponse>;
  selectedTaskKey?: string | null;
  onSelectTask?: (taskKey: string) => void;
}

export function WorkflowDAGView({
  tasks,
  runtimeTasks = {},
  selectedTaskKey,
  onSelectTask,
}: WorkflowDAGViewProps) {
  // Compute topological levels (layers) for clean DAG column layout
  const levels = useMemo(() => {
    const taskMap = new Map<string, TaskSpecSchema>(tasks.map((t) => [t.task_key, t]));
    const levelMap = new Map<string, number>();

    const getLevel = (key: string, visited: Set<string> = new Set()): number => {
      if (levelMap.has(key)) return levelMap.get(key)!;
      if (visited.has(key)) return 0; // Guard cyclic
      visited.add(key);

      const task = taskMap.get(key);
      if (!task || task.depends_on.length === 0) {
        levelMap.set(key, 0);
        return 0;
      }

      const maxDepLevel = Math.max(
        ...task.depends_on.map((dep) => getLevel(dep, new Set(visited)))
      );
      const lvl = maxDepLevel + 1;
      levelMap.set(key, lvl);
      return lvl;
    };

    tasks.forEach((t) => getLevel(t.task_key));

    const maxLevel = Math.max(0, ...Array.from(levelMap.values()));
    const cols: TaskSpecSchema[][] = Array.from({ length: maxLevel + 1 }, () => []);

    tasks.forEach((t) => {
      const lvl = levelMap.get(t.task_key) || 0;
      cols[lvl].push(t);
    });

    return cols;
  }, [tasks]);

  return (
    <div className="w-full rounded-lg border border-zinc-800 bg-zinc-950/70 p-6 overflow-x-auto">
      <div className="flex items-center justify-between mb-4 pb-2 border-b border-zinc-800/80 text-xs font-mono-data text-zinc-400">
        <span className="flex items-center gap-2">
          <span>DAG Topology</span>
          <span className="text-zinc-600">·</span>
          <span>{tasks.length} Nodes</span>
        </span>
        <div className="flex items-center gap-3 text-[11px]">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded bg-zinc-700" />
            <span>Prerequisite Dependency Flow →</span>
          </span>
        </div>
      </div>

      <div className="flex items-start gap-8 min-w-max py-4">
        {levels.map((columnTasks, colIdx) => (
          <div key={colIdx} className="flex flex-col gap-4 min-w-[240px]">
            <div className="text-[10px] font-mono-data uppercase tracking-wider text-zinc-500 px-1">
              Layer {colIdx + 1} ({columnTasks.length} {columnTasks.length === 1 ? "task" : "tasks"})
            </div>

            {columnTasks.map((task) => {
              const runtime = runtimeTasks[task.task_key];
              const statusCfg = runtime
                ? TASK_STATUS_CONFIG[runtime.status]
                : null;
              const isSelected = selectedTaskKey === task.task_key;

              return (
                <div
                  key={task.task_key}
                  onClick={() => onSelectTask?.(task.task_key)}
                  className={cn(
                    "p-3.5 rounded-lg border bg-zinc-900/90 text-left transition-all cursor-pointer relative group",
                    isSelected
                      ? "border-zinc-400 ring-1 ring-zinc-400 bg-zinc-800/70"
                      : "border-zinc-800 hover:border-zinc-700 hover:bg-zinc-850"
                  )}
                >
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <span className="text-xs font-semibold text-zinc-100 tracking-tight line-clamp-1">
                      {task.name}
                    </span>
                    {statusCfg ? (
                      <Badge variant={statusCfg.variant} size="sm" dot>
                        {statusCfg.label}
                      </Badge>
                    ) : (
                      <Badge variant="neutral" size="sm">
                        SPEC
                      </Badge>
                    )}
                  </div>

                  <div className="text-[11px] font-mono-data text-zinc-400 flex items-center gap-1 mb-2">
                    <Bot className="w-3 h-3 text-zinc-400 shrink-0" />
                    <span className="truncate text-zinc-300">{task.agent_id}</span>
                  </div>

                  {/* Task Metadata tags */}
                  <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-zinc-800/60 text-[10px] font-mono-data">
                    <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                      key: {task.task_key}
                    </span>
                    {task.approval_gate?.required ? (
                      <span className="px-1.5 py-0.5 rounded bg-amber-950/70 text-amber-300 border border-amber-800/50 flex items-center gap-0.5">
                        <ShieldCheck className="w-2.5 h-2.5" />
                        Gate
                      </span>
                    ) : null}
                    {task.evaluation_gate?.enabled ? (
                      <span className="px-1.5 py-0.5 rounded bg-blue-950/70 text-blue-300 border border-blue-800/50 flex items-center gap-0.5">
                        <RotateCcw className="w-2.5 h-2.5" />
                        Eval
                      </span>
                    ) : null}
                  </div>

                  {/* Depends On labels */}
                  {task.depends_on.length > 0 ? (
                    <div className="mt-2 text-[10px] font-mono-data text-zinc-500 truncate">
                      depends: {task.depends_on.join(", ")}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
