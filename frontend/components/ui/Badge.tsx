import React from "react";
import { cn } from "@/lib/utils/cn";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?:
    | "default"
    | "success"
    | "warning"
    | "danger"
    | "info"
    | "neutral"
    | "outline";
  size?: "sm" | "md";
  dot?: boolean;
}

export function Badge({
  className,
  variant = "default",
  size = "sm",
  dot = false,
  children,
  ...props
}: BadgeProps) {
  const variantStyles = {
    default: "bg-zinc-800 text-zinc-200 border-zinc-700",
    success:
      "bg-emerald-950/60 text-emerald-300 border-emerald-800/80 [data-dot]:bg-emerald-400",
    warning:
      "bg-amber-950/60 text-amber-300 border-amber-800/80 [data-dot]:bg-amber-400",
    danger:
      "bg-rose-950/60 text-rose-300 border-rose-800/80 [data-dot]:bg-rose-400",
    info: "bg-blue-950/60 text-blue-300 border-blue-800/80 [data-dot]:bg-blue-400",
    neutral: "bg-zinc-900 text-zinc-400 border-zinc-800 [data-dot]:bg-zinc-500",
    outline: "bg-transparent text-zinc-300 border-zinc-700",
  };

  const dotColors = {
    default: "bg-zinc-400",
    success: "bg-emerald-400",
    warning: "bg-amber-400",
    danger: "bg-rose-400",
    info: "bg-blue-400",
    neutral: "bg-zinc-500",
    outline: "bg-zinc-400",
  };

  const sizeStyles = {
    sm: "px-2 py-0.5 text-[11px] gap-1.5 leading-none",
    md: "px-2.5 py-1 text-xs gap-1.5",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center font-medium font-mono-data rounded border tracking-tight shrink-0",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={cn("w-1.5 h-1.5 rounded-full shrink-0", dotColors[variant])}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}
