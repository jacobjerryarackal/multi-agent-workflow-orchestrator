"use client";

import React, { useEffect, useState } from "react";
import { getAgents } from "@/lib/api/agents";
import { AgentSummaryResponse } from "@/lib/types/api";
import { AgentCard } from "@/components/agents/AgentCard";
import { LoadingState, ErrorState } from "@/components/ui/LoadingState";
import { Button } from "@/components/ui/Button";
import { Bot, RefreshCw, Cpu, ShieldCheck } from "lucide-react";

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentSummaryResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAgents = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAgents();
      setAgents(res.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load agent catalog.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAgents();
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
            <Bot className="w-5 h-5 text-zinc-300" />
            Specialized Agent Catalog
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Model-specialized agents with typed Pydantic contracts, structured outputs, and role prompt specifications.
          </p>
        </div>

        <Button variant="secondary" size="sm" onClick={loadAgents} isLoading={isLoading}>
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </Button>
      </div>

      {isLoading ? (
        <LoadingState message="Loading registered specialized agents..." />
      ) : error ? (
        <ErrorState title="Agent Catalog Error" error={error} onRetry={loadAgents} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <AgentCard key={agent.agent_id} agent={agent} />
          ))}
        </div>
      )}
    </div>
  );
}
