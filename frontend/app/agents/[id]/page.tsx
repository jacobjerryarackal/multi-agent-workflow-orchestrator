"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getAgent } from "@/lib/api/agents";
import { AgentSummaryResponse } from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { LoadingState, ErrorState } from "@/components/ui/LoadingState";
import { ArrowLeft, Bot, Cpu, ShieldCheck, FileCode, CheckCircle2 } from "lucide-react";

export default function AgentDetailPage() {
  const params = useParams();
  const agentId = params?.id as string;

  const [agent, setAgent] = useState<AgentSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"input" | "output">("input");

  const loadAgent = React.useCallback(async () => {
    if (!agentId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await getAgent(agentId);
      setAgent(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load agent specification.");
    } finally {
      setIsLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    loadAgent();
  }, [loadAgent]);

  if (isLoading && !agent) {
    return <LoadingState message="Loading agent specification and schema contracts..." />;
  }

  if (error && !agent) {
    return (
      <ErrorState
        title="Agent Specification Error"
        error={error}
        onRetry={loadAgent}
      />
    );
  }

  if (!agent) return null;

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto">
      {/* Header & Back Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <Link href="/agents">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
                <Bot className="w-5 h-5 text-zinc-300" />
                {agent.name}
              </h1>
              <Badge variant="neutral">v{agent.version}</Badge>
            </div>
            <p className="text-xs text-zinc-400 font-mono-data mt-0.5">
              Identifier: <strong className="text-zinc-200">{agent.agent_id}</strong>
            </p>
          </div>
        </div>
      </div>

      {/* Overview & Metadata Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="md:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Agent Role & Capabilities</CardTitle>
            <CardDescription className="leading-relaxed mt-1">
              {agent.description}
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-2 flex flex-col gap-2">
            <span className="text-[11px] font-mono-data text-zinc-400 uppercase">
              Registered Capabilities
            </span>
            <div className="flex flex-wrap gap-1.5">
              {agent.capabilities.map((cap) => (
                <Badge key={cap} variant="outline" size="sm">
                  {cap}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Runtime Provider</CardTitle>
            <CardDescription>Model binding and provider settings</CardDescription>
          </CardHeader>
          <CardContent className="pt-1 flex flex-col gap-3 text-xs font-mono-data text-zinc-400">
            <div className="flex items-center justify-between pb-1.5 border-b border-zinc-800">
              <span>Provider</span>
              <span className="text-zinc-200">Google Gemini</span>
            </div>
            <div className="flex items-center justify-between pb-1.5 border-b border-zinc-800">
              <span>Default Model</span>
              <span className="text-zinc-200">gemini-2.5-flash</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Reasoning Model</span>
              <span className="text-zinc-200">gemini-2.5-pro</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Contract Schemas Inspector */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div className="flex items-center gap-2">
            <FileCode className="w-4 h-4 text-zinc-400" />
            <CardTitle className="text-sm">Pydantic Contract Schemas</CardTitle>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setActiveTab("input")}
              className={`px-2.5 py-1 text-xs font-medium rounded border transition-colors ${
                activeTab === "input"
                  ? "bg-zinc-100 text-zinc-900 border-white font-semibold"
                  : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200"
              }`}
            >
              Input Contract Schema
            </button>
            <button
              onClick={() => setActiveTab("output")}
              className={`px-2.5 py-1 text-xs font-medium rounded border transition-colors ${
                activeTab === "output"
                  ? "bg-zinc-100 text-zinc-900 border-white font-semibold"
                  : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200"
              }`}
            >
              Output Contract Schema
            </button>
          </div>
        </CardHeader>

        <CardContent className="pt-0">
          {activeTab === "input" ? (
            <CodeBlock code={agent.input_schema} language="json" maxHeight="max-h-[500px]" />
          ) : (
            <CodeBlock code={agent.output_schema} language="json" maxHeight="max-h-[500px]" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
