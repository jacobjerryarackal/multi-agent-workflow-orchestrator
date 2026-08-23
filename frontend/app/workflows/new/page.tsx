import React from "react";
import Link from "next/link";
import { WorkflowCreatorWizard } from "@/components/workflows/WorkflowCreatorWizard";
import { ArrowLeft, GitFork } from "lucide-react";
import { Button } from "@/components/ui/Button";

export default function NewWorkflowPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <Link href="/workflows">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
              <GitFork className="w-5 h-5 text-zinc-300" />
              Define New Multi-Agent Workflow
            </h1>
            <p className="text-xs text-zinc-400 mt-0.5">
              Author a DAG pipeline with structured dependencies, model-specialized agents, and quality gates.
            </p>
          </div>
        </div>
      </div>

      <WorkflowCreatorWizard />
    </div>
  );
}
