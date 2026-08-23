import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "./Button";
import { cn } from "@/lib/utils/cn";

export function LoadingState({
  message = "Loading orchestrator data...",
  className,
}: {
  message?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center p-12 text-center text-zinc-400 gap-3",
        className
      )}
    >
      <div className="w-5 h-5 border-2 border-zinc-500 border-t-zinc-200 rounded-full animate-spin" />
      <span className="text-xs font-mono-data text-zinc-400">{message}</span>
    </div>
  );
}

export function ErrorState({
  title = "Failed to load data",
  error,
  correlationId,
  onRetry,
  className,
}: {
  title?: string;
  error?: string | Error | null;
  correlationId?: string;
  onRetry?: () => void;
  className?: string;
}) {
  const errorMessage =
    typeof error === "string"
      ? error
      : error?.message || "An unexpected network or server exception occurred.";

  return (
    <div
      className={cn(
        "rounded-lg border border-rose-900/60 bg-rose-950/20 p-5 text-zinc-200 flex flex-col gap-3 my-3",
        className
      )}
    >
      <div className="flex items-start gap-3">
        <div className="p-1.5 rounded bg-rose-900/50 text-rose-300 shrink-0 mt-0.5 border border-rose-800">
          <AlertTriangle className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-rose-200">{title}</h4>
          <p className="text-xs text-rose-300/80 mt-1 leading-relaxed break-words">
            {errorMessage}
          </p>
          {correlationId ? (
            <div className="mt-2 text-[11px] font-mono-data text-zinc-400">
              Correlation ID: <span className="text-zinc-300 select-all">{correlationId}</span>
            </div>
          ) : null}
        </div>
      </div>
      {onRetry ? (
        <div className="flex justify-end pt-2 border-t border-rose-900/40">
          <Button variant="secondary" size="sm" onClick={onRetry}>
            <RefreshCw className="w-3.5 h-3.5" />
            Retry Request
          </Button>
        </div>
      ) : null}
    </div>
  );
}
