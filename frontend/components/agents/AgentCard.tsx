"use client";

import React, { useState } from "react";
import { AgentSummaryResponse } from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { Bot, Code2, Cpu, CheckCircle } from "lucide-react";

export interface AgentCardProps {
  agent: AgentSummaryResponse;
}

export function AgentCard({ agent }: AgentCardProps) {
  const [isSchemaModalOpen, setIsSchemaModalOpen] = useState(false);
  const [schemaTab, setSchemaTab] = useState<"input" | "output">("input");

  return (
    <>
      <Card className="border-zinc-800 bg-zinc-900/40 hover:border-zinc-700 transition-colors flex flex-col justify-between">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300">
                <Bot className="w-4 h-4" />
              </div>
              <div>
                <CardTitle className="text-sm text-zinc-100">{agent.name}</CardTitle>
                <span className="text-[11px] font-mono-data text-zinc-500">
                  {agent.agent_id}
                </span>
              </div>
            </div>
            <Badge variant="neutral">v{agent.version}</Badge>
          </div>
          <CardDescription className="line-clamp-2 mt-2">
            {agent.description}
          </CardDescription>
        </CardHeader>

        <CardContent className="pt-2 flex flex-col gap-3">
          {/* Capabilities */}
          <div className="flex flex-wrap gap-1">
            {agent.capabilities.map((cap) => (
              <Badge key={cap} variant="outline" size="sm">
                {cap}
              </Badge>
            ))}
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-zinc-800/60 text-xs">
            <div className="flex items-center gap-1.5 font-mono-data text-zinc-400 text-[11px]">
              <Cpu className="w-3 h-3 text-zinc-500" />
              <span>Gemini 2.5 Flash</span>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsSchemaModalOpen(true)}
              className="h-7 text-[11px]"
            >
              <Code2 className="w-3 h-3" />
              Contracts
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Schema Inspector Modal */}
      <Modal
        isOpen={isSchemaModalOpen}
        onClose={() => setIsSchemaModalOpen(false)}
        title={`${agent.name} Contract Schemas`}
        description={`Pydantic input and structured output schemas for agent: ${agent.agent_id}`}
        maxWidth="xl"
      >
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
            <button
              onClick={() => setSchemaTab("input")}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                schemaTab === "input"
                  ? "bg-zinc-100 text-zinc-900 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Input Contract Schema
            </button>
            <button
              onClick={() => setSchemaTab("output")}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                schemaTab === "output"
                  ? "bg-zinc-100 text-zinc-900 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Output Contract Schema
            </button>
          </div>

          {schemaTab === "input" ? (
            <CodeBlock
              code={agent.input_schema}
              language="json"
              maxHeight="max-h-96"
            />
          ) : (
            <CodeBlock
              code={agent.output_schema}
              language="json"
              maxHeight="max-h-96"
            />
          )}
        </div>
      </Modal>
    </>
  );
}
