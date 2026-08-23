"use client";

import React, { useState } from "react";
import Link from "next/link";
import { WorkflowResponse } from "@/lib/types/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatDate, formatShortId } from "@/lib/utils/formatting";
import { GitFork, Play, Search, ArrowRight } from "lucide-react";

export interface WorkflowTableProps {
  workflows: WorkflowResponse[];
  onTriggerExecution?: (workflow: WorkflowResponse) => void;
}

export function WorkflowTable({
  workflows,
  onTriggerExecution,
}: WorkflowTableProps) {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredWorkflows = workflows.filter(
    (w) =>
      w.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      w.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      w.id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="Search workflows by name or ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full h-8 pl-8 pr-3 text-xs bg-zinc-900 border border-zinc-800 rounded text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-400"
          />
        </div>
        <div className="text-xs font-mono-data text-zinc-400">
          Showing {filteredWorkflows.length} of {workflows.length} workflows
        </div>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">#</TableHead>
              <TableHead>Workflow Name</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Tasks</TableHead>
              <TableHead>Max Duration</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredWorkflows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-zinc-500">
                  No workflows matched the search filter.
                </TableCell>
              </TableRow>
            ) : (
              filteredWorkflows.map((workflow, idx) => (
                <TableRow key={workflow.id}>
                  <TableCell className="font-mono-data text-zinc-500">
                    {idx + 1}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <Link
                        href={`/workflows/${workflow.id}`}
                        className="font-medium text-zinc-100 hover:text-white hover:underline flex items-center gap-1.5"
                      >
                        <GitFork className="w-3.5 h-3.5 text-zinc-400" />
                        {workflow.name}
                      </Link>
                      <span className="text-[11px] text-zinc-400 line-clamp-1 mt-0.5">
                        {workflow.description}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="neutral">v{workflow.version}</Badge>
                  </TableCell>
                  <TableCell className="font-mono-data">
                    <span className="text-zinc-200">{workflow.tasks.length}</span>{" "}
                    <span className="text-zinc-500">nodes</span>
                  </TableCell>
                  <TableCell className="font-mono-data text-zinc-400">
                    {workflow.max_workflow_duration_seconds}s
                  </TableCell>
                  <TableCell className="font-mono-data text-zinc-400">
                    {formatDate(workflow.created_at, { relative: true })}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      {onTriggerExecution ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => onTriggerExecution(workflow)}
                          className="h-7 text-[11px]"
                        >
                          <Play className="w-3 h-3 text-emerald-400" />
                          Run
                        </Button>
                      ) : null}
                      <Link href={`/workflows/${workflow.id}`}>
                        <Button variant="ghost" size="sm" className="h-7 text-[11px]">
                          View
                          <ArrowRight className="w-3 h-3" />
                        </Button>
                      </Link>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
