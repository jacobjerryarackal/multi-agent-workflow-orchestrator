"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  GitFork,
  PlayCircle,
  Bot,
  Server,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  {
    label: "Operations Console",
    href: "/",
    icon: Activity,
    exact: true,
  },
  {
    label: "Workflows",
    href: "/workflows",
    icon: GitFork,
  },
  {
    label: "Executions",
    href: "/executions",
    icon: PlayCircle,
  },
  {
    label: "Specialized Agents",
    href: "/agents",
    icon: Bot,
  },
  {
    label: "System Health",
    href: "/system",
    icon: Server,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 border-r border-zinc-800 bg-zinc-950 flex flex-col shrink-0 h-screen sticky top-0">
      {/* Brand Header */}
      <div className="h-14 px-4 border-b border-zinc-800 flex items-center gap-2.5">
        <div className="w-7 h-7 rounded bg-zinc-900 border border-zinc-700 flex items-center justify-center text-zinc-100 font-semibold shadow-inner">
          <Layers className="w-4 h-4 text-zinc-300" />
        </div>
        <div className="flex flex-col min-w-0">
          <span className="text-xs font-semibold text-zinc-100 tracking-tight truncate">
            Workflow Orchestrator
          </span>
          <span className="text-[10px] font-mono-data text-zinc-500 uppercase tracking-wider">
            Multi-Agent Engine
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2.5 py-4 space-y-1 overflow-y-auto">
        <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500 font-mono-data">
          Control Plane
        </div>
        {NAV_ITEMS.map((item) => {
          const isActive = item.exact
            ? pathname === item.href
            : pathname.startsWith(item.href);
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 px-2.5 py-2 rounded text-xs font-medium transition-colors select-none group",
                isActive
                  ? "bg-zinc-800/90 text-zinc-100 font-semibold border border-zinc-700/60"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-transparent"
              )}
            >
              <Icon
                className={cn(
                  "w-4 h-4 shrink-0 transition-colors",
                  isActive
                    ? "text-zinc-100"
                    : "text-zinc-400 group-hover:text-zinc-200"
                )}
              />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer System Status Indicator */}
      <div className="p-3 border-t border-zinc-800/80 bg-zinc-950/50">
        <div className="flex items-center justify-between text-[11px] font-mono-data text-zinc-400">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-zinc-300">Engine Online</span>
          </div>
          <span className="text-zinc-500 text-[10px]">v1.0.0</span>
        </div>
      </div>
    </aside>
  );
}
