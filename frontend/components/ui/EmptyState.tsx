import React from "react";
import { cn } from "@/lib/utils/cn";
import { LucideIcon } from "lucide-react";

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center p-8 text-center rounded-lg border border-dashed border-zinc-800 bg-zinc-900/20 my-2",
        className
      )}
    >
      {Icon ? (
        <div className="p-2.5 mb-3 rounded-full bg-zinc-800/80 text-zinc-400 border border-zinc-700/60">
          <Icon className="w-5 h-5" />
        </div>
      ) : null}
      <h4 className="text-sm font-medium text-zinc-200">{title}</h4>
      {description ? (
        <p className="text-xs text-zinc-400 max-w-sm mt-1 mb-4 leading-normal">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
