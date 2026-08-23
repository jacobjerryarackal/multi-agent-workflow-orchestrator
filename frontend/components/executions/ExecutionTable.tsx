"use client";

import React, { useState } from "react";
import Link from "next/link";
import { WorkflowExecutionSummaryResponse } from "@/lib/types/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatDate, formatDuration, formatShortId } from "@/lib/utils/formatting";
import { WORKFLOW_STATUS_CONFIG } from "@/lib/types/status";
import { PlayCircle, ArrowRight, Filter, Search } from "lucide-react";

export interface ExecutionTableProps {
  executions: WorkflowExecutionSummaryResponse[];
  workflowNameMap?: Record<string, string>;
}

export function ExecutionTable({
  executions,
  workflowNameMap = {},
}: ExecutionTableProps) {
  const [filterStatus, setFilterStatus] = useState<string>("ALL");
  const [search, setSearch] = useState<string>("");

  const filtered = executions.filter((exec) => {
    const matchesStatus = filterStatus === "ALL" || exec.status === filterStatus;
    const matchesSearch =
      exec.id.toLowerCase().includes(search.toLowerCase()) ||
      exec.workflow_id.toLowerCase().includes(search.toLowerCase()) ||
      (exec.idempotency_key &&
        exec.idempotency_key.toLowerCase().includes(search.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="flex flex-col gap-3">
      {/* Search & Status Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-1 max-w-sm">
          <div className="relative w-full">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder="Filter by execution ID or key..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-8 pl-8 pr-3 text-xs bg-zinc-900 border border-zinc-800 rounded text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-400"
            />
          </div>
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto">
          {["ALL", "RUNNING", "WAITING_APPROVAL", "COMPLETED", "FAILED", "CANCELLED"].map((st) => (
            <button
              key={st}
              onClick={() => setFilterStatus(st)}
              className={`px-2.5 py-1 rounded text-[11px] font-mono-data border transition-colors ${
                filterStatus === st
                  ? "bg-zinc-100 text-zinc-900 border-white font-medium"
                  : "bg-zinc-900/60 text-zinc-400 border-zinc-800 hover:text-zinc-200"
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Execution ID</TableHead>
              <TableHead>Workflow</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Trigger</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-zinc-500">
                  No executions match the active filters.
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((exec) => {
                const statusCfg = WORKFLOW_STATUS_CONFIG[exec.status] || {
                  label: exec.status,
                  variant: "neutral",
                };
                const wfName = workflowNameMap[exec.workflow_id] || formatShortId(exec.workflow_id);

                return (
                  <TableRow key={exec.id}>
                    <TableCell className="font-mono-data">
                      <Link
                        href={`/executions/${exec.id}`}
                        className="text-zinc-100 hover:text-white font-medium hover:underline flex items-center gap-1.5"
                      >
                        <PlayCircle className="w-3.5 h-3.5 text-zinc-400" />
                        {formatShortId(exec.id, 8)}
                      </Link>
                      {exec.idempotency_key ? (
                        <span className="text-[10px] text-zinc-500 block">
                          idem: {formatShortId(exec.idempotency_key, 12)}
                        </span>
                      ) : null}
                    </TableCell>

                    <TableCell>
                      <Link
                        href={`/workflows/${exec.workflow_id}`}
                        className="text-xs text-zinc-300 hover:text-white hover:underline truncate max-w-[200px] block"
                      >
                        {wfName}
                      </Link>
                    </TableCell>

                    <TableCell>
                      <Badge variant={statusCfg.variant} dot>
                        {statusCfg.label}
                      </Badge>
                    </TableCell>

                    <TableCell className="font-mono-data text-zinc-400 uppercase text-[11px]">
                      {exec.trigger_type}
                    </TableCell>

                    <TableCell className="font-mono-data text-zinc-400">
                      {formatDate(exec.started_at || exec.created_at, {
                        relative: true,
                      })}
                    </TableCell>

                    <TableCell className="font-mono-data text-zinc-400">
                      {formatDuration(exec.execution_duration_ms)}
                    </TableCell>

                    <TableCell className="text-right">
                      <Link href={`/executions/${exec.id}`}>
                        <Button variant="ghost" size="sm" className="h-7 text-[11px]">
                          Inspect
                          <ArrowRight className="w-3 h-3" />
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
