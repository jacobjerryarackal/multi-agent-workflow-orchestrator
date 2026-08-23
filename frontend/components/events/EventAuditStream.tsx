"use client";

import React, { useState } from "react";
import { EventResponse } from "@/lib/types/api";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/utils/formatting";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { Activity, ShieldCheck, Play, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";

export interface EventAuditStreamProps {
  events: EventResponse[];
}

export function EventAuditStream({ events }: EventAuditStreamProps) {
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  const getEventBadgeVariant = (eventType: string) => {
    if (eventType.includes("FAIL") || eventType.includes("ERROR") || eventType.includes("CANCEL"))
      return "danger";
    if (eventType.includes("COMPLETED") || eventType.includes("PASSED"))
      return "success";
    if (eventType.includes("APPROVAL") || eventType.includes("PAUSED"))
      return "warning";
    if (eventType.includes("STARTED") || eventType.includes("RUNNING"))
      return "info";
    return "neutral";
  };

  return (
    <div className="flex flex-col gap-2">
      {events.length === 0 ? (
        <div className="text-center py-6 text-xs text-zinc-500 font-mono-data">
          No audit telemetry events recorded yet.
        </div>
      ) : (
        events.map((event) => {
          const isExpanded = expandedEventId === event.id;
          const hasPayload =
            event.payload && Object.keys(event.payload).length > 0;

          return (
            <div
              key={event.id}
              className="rounded border border-zinc-800/80 bg-zinc-900/40 text-xs text-zinc-300 overflow-hidden"
            >
              <div
                onClick={() =>
                  hasPayload ? setExpandedEventId(isExpanded ? null : event.id) : null
                }
                className={`p-2.5 flex items-center justify-between gap-3 ${
                  hasPayload ? "cursor-pointer hover:bg-zinc-800/40 select-none" : ""
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="text-[11px] font-mono-data text-zinc-500 shrink-0">
                    {formatDate(event.timestamp, { includeTime: true })}
                  </span>

                  <Badge variant={getEventBadgeVariant(event.event_type)} size="sm">
                    {event.event_type}
                  </Badge>

                  {event.task_key ? (
                    <span className="text-[11px] font-mono-data text-zinc-400 truncate">
                      node: <strong className="text-zinc-200">{event.task_key}</strong>
                    </span>
                  ) : null}

                  <span className="text-[10px] font-mono-data text-zinc-500">
                    actor: {event.actor}
                  </span>
                </div>

                <div className="flex items-center gap-2 shrink-0 text-[11px] font-mono-data text-zinc-500">
                  {hasPayload ? (
                    <span>
                      {isExpanded ? (
                        <ChevronUp className="w-3.5 h-3.5" />
                      ) : (
                        <ChevronDown className="w-3.5 h-3.5" />
                      )}
                    </span>
                  ) : null}
                </div>
              </div>

              {isExpanded && hasPayload ? (
                <div className="p-3 border-t border-zinc-800 bg-zinc-950/60">
                  <span className="text-[10px] font-mono-data text-zinc-500 uppercase block mb-1">
                    Event Telemetry Payload
                  </span>
                  <CodeBlock code={event.payload} language="json" maxHeight="max-h-40" />
                </div>
              ) : null}
            </div>
          );
        })
      )}
    </div>
  );
}
