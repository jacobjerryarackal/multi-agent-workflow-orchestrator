"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { createWorkflow } from "@/lib/api/workflows";
import { getAgents } from "@/lib/api/agents";
import {
  AgentSummaryResponse,
  TaskSpecSchema,
  WorkflowCreateRequest,
} from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { CodeBlock } from "@/components/ui/CodeBlock";
import {
  Plus,
  Trash2,
  GitFork,
  CheckCircle2,
  ShieldCheck,
  RotateCcw,
  ArrowLeft,
  ArrowRight,
  AlertCircle,
} from "lucide-react";

export function WorkflowCreatorWizard() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [agents, setAgents] = useState<AgentSummaryResponse[]>([]);
  const [isLoadingAgents, setIsLoadingAgents] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form State
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [maxDuration, setMaxDuration] = useState(600);
  const [maxParallelTasks, setMaxParallelTasks] = useState(5);
  const [tasks, setTasks] = useState<TaskSpecSchema[]>([
    {
      task_key: "task_1",
      name: "Decompose Objective",
      agent_id: "planner_agent",
      depends_on: [],
      input_mappings: {},
      static_inputs: { objective: "Analyze request" },
      timeout_seconds: 60,
      retry_policy: {
        max_attempts: 3,
        initial_interval_seconds: 2,
        backoff_multiplier: 2,
        jitter: true,
        retryable_categories: ["INFRASTRUCTURE_PROVIDER_FAILURE", "TEMPORAL_FAILURE"],
      },
      approval_gate: {
        required: false,
        approver_roles: ["admin"],
        timeout_seconds: 86400,
        auto_action_on_timeout: "ESCALATE",
      },
      evaluation_gate: {
        enabled: false,
        evaluator_name: "composite_quality_evaluator",
        min_pass_score: 0.8,
        max_revisions: 2,
        deterministic_rules: [],
        criteria: {},
        rejection_policy: "FAIL",
      },
    },
  ]);

  useEffect(() => {
    async function loadAgents() {
      try {
        const res = await getAgents();
        setAgents(res.items);
      } catch {
        // Fallback default agent IDs if backend is offline during render
        setAgents([
          { agent_id: "planner_agent", name: "Workflow Planner", description: "", version: "1.0", capabilities: [], input_schema: {}, output_schema: {} },
          { agent_id: "researcher_agent", name: "Researcher", description: "", version: "1.0", capabilities: [], input_schema: {}, output_schema: {} },
          { agent_id: "analyst_agent", name: "Analyst", description: "", version: "1.0", capabilities: [], input_schema: {}, output_schema: {} },
          { agent_id: "reviewer_agent", name: "Reviewer", description: "", version: "1.0", capabilities: [], input_schema: {}, output_schema: {} },
          { agent_id: "synthesizer_agent", name: "Synthesizer", description: "", version: "1.0", capabilities: [], input_schema: {}, output_schema: {} },
        ]);
      } finally {
        setIsLoadingAgents(false);
      }
    }
    loadAgents();
  }, []);

  const handleAddTask = () => {
    const nextIdx = tasks.length + 1;
    const prevKey = tasks.length > 0 ? tasks[tasks.length - 1].task_key : "";
    const newTask: TaskSpecSchema = {
      task_key: `task_${nextIdx}`,
      name: `Step ${nextIdx}`,
      agent_id: agents[0]?.agent_id || "researcher_agent",
      depends_on: prevKey ? [prevKey] : [],
      input_mappings: {},
      static_inputs: {},
      timeout_seconds: 60,
      retry_policy: {
        max_attempts: 3,
        initial_interval_seconds: 2,
        backoff_multiplier: 2,
        jitter: true,
        retryable_categories: ["INFRASTRUCTURE_PROVIDER_FAILURE"],
      },
      approval_gate: {
        required: false,
        approver_roles: ["admin"],
        timeout_seconds: 86400,
        auto_action_on_timeout: "ESCALATE",
      },
      evaluation_gate: {
        enabled: false,
        evaluator_name: "composite_quality_evaluator",
        min_pass_score: 0.8,
        max_revisions: 2,
        deterministic_rules: [],
        criteria: {},
        rejection_policy: "FAIL",
      },
    };
    setTasks([...tasks, newTask]);
  };

  const handleRemoveTask = (idx: number) => {
    if (tasks.length <= 1) return;
    const removedKey = tasks[idx].task_key;
    const updated = tasks.filter((_, i) => i !== idx).map((t) => ({
      ...t,
      depends_on: t.depends_on.filter((d) => d !== removedKey),
    }));
    setTasks(updated);
  };

  const handleUpdateTask = (idx: number, patch: Partial<TaskSpecSchema>) => {
    const updated = [...tasks];
    updated[idx] = { ...updated[idx], ...patch };
    setTasks(updated);
  };

  const validateTasks = (taskList: TaskSpecSchema[]): string | null => {
    if (taskList.length === 0) return "At least one task node is required in the workflow.";
    const keySet = new Set<string>();
    for (let i = 0; i < taskList.length; i++) {
      const t = taskList[i];
      const key = t.task_key.trim();
      if (!key) return `Task #${i + 1} must have a non-empty task key.`;
      if (!/^[a-zA-Z0-9_-]+$/.test(key)) {
        return `Task key '${key}' contains invalid characters. Use alphanumeric characters, dashes, or underscores.`;
      }
      if (keySet.has(key)) {
        return `Duplicate task key '${key}'. All task keys in the DAG must be unique.`;
      }
      keySet.add(key);

      if (!t.name.trim()) return `Task '${key}' must have a descriptive name.`;
      if (t.depends_on.includes(key)) {
        return `Task '${key}' cannot depend on itself.`;
      }
    }

    // Cyclic dependency detection (DFS)
    const graph = new Map<string, string[]>();
    taskList.forEach((t) => graph.set(t.task_key, t.depends_on));
    const visited = new Set<string>();
    const recStack = new Set<string>();

    function hasCycle(node: string): boolean {
      visited.add(node);
      recStack.add(node);
      const neighbors = graph.get(node) || [];
      for (const neighbor of neighbors) {
        if (!visited.has(neighbor)) {
          if (hasCycle(neighbor)) return true;
        } else if (recStack.has(neighbor)) {
          return true;
        }
      }
      recStack.delete(node);
      return false;
    }

    for (const node of Array.from(graph.keys())) {
      if (!visited.has(node)) {
        if (hasCycle(node)) {
          return "Cyclic dependency detected in task graph. Workflow DAG must be acyclic.";
        }
      }
    }

    return null;
  };

  const handleProceedToReview = () => {
    const taskError = validateTasks(tasks);
    if (taskError) {
      setError(taskError);
      return;
    }
    setError(null);
    setStep(3);
  };

  const handleSubmit = async () => {
    setError(null);
    if (!name.trim()) {
      setError("Workflow name is required.");
      setStep(1);
      return;
    }
    if (!description.trim()) {
      setError("Workflow description is required.");
      setStep(1);
      return;
    }

    const taskError = validateTasks(tasks);
    if (taskError) {
      setError(taskError);
      setStep(2);
      return;
    }

    const payload: WorkflowCreateRequest = {
      name: name.trim(),
      description: description.trim(),
      version: 1,
      tasks,
      max_workflow_duration_seconds: maxDuration,
      max_parallel_tasks: maxParallelTasks,
    };

    setIsSubmitting(true);
    try {
      const created = await createWorkflow(payload);
      router.push(`/workflows/${created.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create workflow.");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto">
      {/* Wizard Step Indicator */}
      <div className="flex items-center justify-between p-4 rounded-lg border border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center gap-3">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono-data font-semibold ${
              step === 1 ? "bg-white text-zinc-900" : "bg-zinc-800 text-zinc-300"
            }`}
          >
            1
          </div>
          <span className="text-xs font-medium text-zinc-200">
            1. Metadata & Limits
          </span>
        </div>
        <div className="h-px w-12 bg-zinc-800" />
        <div className="flex items-center gap-3">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono-data font-semibold ${
              step === 2 ? "bg-white text-zinc-900" : "bg-zinc-800 text-zinc-300"
            }`}
          >
            2
          </div>
          <span className="text-xs font-medium text-zinc-200">
            2. DAG Tasks & Gates
          </span>
        </div>
        <div className="h-px w-12 bg-zinc-800" />
        <div className="flex items-center gap-3">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono-data font-semibold ${
              step === 3 ? "bg-white text-zinc-900" : "bg-zinc-800 text-zinc-300"
            }`}
          >
            3
          </div>
          <span className="text-xs font-medium text-zinc-200">
            3. Review & Deploy
          </span>
        </div>
      </div>

      {error ? (
        <div className="p-3 rounded bg-rose-950/60 border border-rose-800 text-xs text-rose-200 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      ) : null}

      {/* Step 1: Metadata */}
      {step === 1 ? (
        <Card>
          <CardHeader>
            <CardTitle>Workflow Specification Details</CardTitle>
            <CardDescription>
              Define the identity, high-level purpose, and operational timeout parameters.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-zinc-300">
                Workflow Identifier / Name *
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. system_architecture_audit_pipeline"
                className="w-full h-8 px-3 text-xs bg-zinc-900 border border-zinc-800 rounded text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-400"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-zinc-300">
                Description / Purpose *
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="Explain the objective and expected outputs of this workflow..."
                className="w-full p-3 text-xs bg-zinc-900 border border-zinc-800 rounded text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-400"
              />
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-zinc-300">
                  Max Workflow Wall-clock Timeout (seconds)
                </label>
                <input
                  type="number"
                  min={30}
                  max={3600}
                  value={maxDuration}
                  onChange={(e) => setMaxDuration(Number(e.target.value))}
                  className="w-full h-8 px-3 text-xs font-mono-data bg-zinc-900 border border-zinc-800 rounded text-zinc-100 focus:outline-none focus:ring-1 focus:ring-zinc-400"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-zinc-300">
                  Max Parallel Task Concurrency Limit
                </label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={maxParallelTasks}
                  onChange={(e) => setMaxParallelTasks(Number(e.target.value))}
                  className="w-full h-8 px-3 text-xs font-mono-data bg-zinc-900 border border-zinc-800 rounded text-zinc-100 focus:outline-none focus:ring-1 focus:ring-zinc-400"
                />
              </div>
            </div>

            <div className="flex justify-end pt-4 border-t border-zinc-800">
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  if (!name.trim()) {
                    setError("Workflow name is required.");
                    return;
                  }
                  if (!description.trim()) {
                    setError("Description is required.");
                    return;
                  }
                  setError(null);
                  setStep(2);
                }}
              >
                Proceed to Tasks
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Step 2: Tasks & DAG */}
      {step === 2 ? (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-zinc-100">
                DAG Task Specifications
              </h3>
              <p className="text-xs text-zinc-400">
                Configure nodes, prerequisite dependencies, assigned specialized agents, and quality gates.
              </p>
            </div>
            <Button variant="secondary" size="sm" onClick={handleAddTask}>
              <Plus className="w-3.5 h-3.5" />
              Add Task Node
            </Button>
          </div>

          <div className="flex flex-col gap-3">
            {tasks.map((task, idx) => (
              <Card key={idx} className="border-zinc-800 bg-zinc-900/60">
                <CardHeader className="py-2.5 bg-zinc-900/90 flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="neutral">#{idx + 1}</Badge>
                    <span className="text-xs font-semibold text-zinc-200">
                      {task.name || `Task ${idx + 1}`}
                    </span>
                    <span className="text-[11px] font-mono-data text-zinc-500">
                      ({task.task_key})
                    </span>
                  </div>
                  {tasks.length > 1 ? (
                    <button
                      onClick={() => handleRemoveTask(idx)}
                      className="p-1 rounded text-zinc-500 hover:text-rose-400 hover:bg-rose-950/40 transition-colors"
                      title="Remove task node"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  ) : null}
                </CardHeader>
                <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-3">
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-medium text-zinc-400">
                      Task Key (Identifier)
                    </label>
                    <input
                      type="text"
                      value={task.task_key}
                      onChange={(e) =>
                        handleUpdateTask(idx, { task_key: e.target.value })
                      }
                      className="h-7 px-2.5 text-xs font-mono-data bg-zinc-950 border border-zinc-800 rounded text-zinc-100"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-medium text-zinc-400">
                      Task Name
                    </label>
                    <input
                      type="text"
                      value={task.name}
                      onChange={(e) =>
                        handleUpdateTask(idx, { name: e.target.value })
                      }
                      className="h-7 px-2.5 text-xs bg-zinc-950 border border-zinc-800 rounded text-zinc-100"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-medium text-zinc-400">
                      Assigned Agent
                    </label>
                    <select
                      value={task.agent_id}
                      onChange={(e) =>
                        handleUpdateTask(idx, { agent_id: e.target.value })
                      }
                      className="h-7 px-2 text-xs font-mono-data bg-zinc-950 border border-zinc-800 rounded text-zinc-100"
                    >
                      {agents.map((ag) => (
                        <option key={ag.agent_id} value={ag.agent_id}>
                          {ag.name} ({ag.agent_id})
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Depends on selector */}
                  <div className="col-span-full flex flex-col gap-1 pt-2 border-t border-zinc-800/60">
                    <label className="text-[11px] font-medium text-zinc-400">
                      Prerequisite Dependencies (Depends On)
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {tasks
                        .filter((_, otherIdx) => otherIdx !== idx)
                        .map((otherTask) => {
                          const isDep = task.depends_on.includes(
                            otherTask.task_key
                          );
                          return (
                            <button
                              key={otherTask.task_key}
                              type="button"
                              onClick={() => {
                                const newDeps = isDep
                                  ? task.depends_on.filter(
                                      (d) => d !== otherTask.task_key
                                    )
                                  : [...task.depends_on, otherTask.task_key];
                                handleUpdateTask(idx, { depends_on: newDeps });
                              }}
                              className={`px-2 py-1 rounded text-[11px] font-mono-data border transition-colors ${
                                isDep
                                  ? "bg-zinc-100 text-zinc-900 border-white font-medium"
                                  : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:border-zinc-700"
                              }`}
                            >
                              {otherTask.task_key} ({otherTask.name})
                            </button>
                          );
                        })}
                      {tasks.length <= 1 ? (
                        <span className="text-[11px] text-zinc-500 italic">
                          Root node (no other tasks exist yet).
                        </span>
                      ) : null}
                    </div>
                  </div>

                  {/* Gates */}
                  <div className="col-span-full flex items-center gap-6 pt-2 text-xs">
                    <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
                      <input
                        type="checkbox"
                        checked={task.approval_gate?.required || false}
                        onChange={(e) =>
                          handleUpdateTask(idx, {
                            approval_gate: {
                              ...task.approval_gate!,
                              required: e.target.checked,
                            },
                          })
                        }
                        className="rounded border-zinc-700 bg-zinc-950"
                      />
                      <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                      Require Human Approval Gate
                    </label>

                    <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
                      <input
                        type="checkbox"
                        checked={task.evaluation_gate?.enabled || false}
                        onChange={(e) =>
                          handleUpdateTask(idx, {
                            evaluation_gate: {
                              ...task.evaluation_gate!,
                              enabled: e.target.checked,
                            },
                          })
                        }
                        className="rounded border-zinc-700 bg-zinc-950"
                      />
                      <RotateCcw className="w-3.5 h-3.5 text-blue-400" />
                      Enable Quality Evaluation & Revision Loop
                    </label>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-zinc-800">
            <Button variant="ghost" size="sm" onClick={() => setStep(1)}>
              <ArrowLeft className="w-3.5 h-3.5" />
              Back to Metadata
            </Button>
            <Button variant="primary" size="sm" onClick={handleProceedToReview}>
              Review Specification
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      ) : null}

      {/* Step 3: Review & Submit */}
      {step === 3 ? (
        <Card>
          <CardHeader>
            <CardTitle>Review Specification JSON</CardTitle>
            <CardDescription>
              Verify the generated multi-agent DAG specification before committing to PostgreSQL.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <CodeBlock
              code={{
                name,
                version: 1,
                description,
                max_workflow_duration_seconds: maxDuration,
                max_parallel_tasks: maxParallelTasks,
                tasks,
              }}
              language="json"
            />

            <div className="flex items-center justify-between pt-4 border-t border-zinc-800">
              <Button variant="ghost" size="sm" onClick={() => setStep(2)}>
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Edit Tasks
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSubmit}
                isLoading={isSubmitting}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                Register Workflow
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
