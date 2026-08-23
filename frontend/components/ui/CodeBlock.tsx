"use client";

import React, { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export interface CodeBlockProps {
  code: string | object;
  language?: string;
  className?: string;
  maxHeight?: string;
}

export function CodeBlock({
  code,
  language = "json",
  className,
  maxHeight = "max-h-80",
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const formattedCode =
    typeof code === "string"
      ? code
      : JSON.stringify(code, null, 2);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(formattedCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback if clipboard API is restricted
    }
  };

  return (
    <div className={cn("relative group rounded-md border border-zinc-800 bg-black/70 overflow-hidden", className)}>
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900/80 border-b border-zinc-800 text-[11px] font-mono-data text-zinc-400">
        <span>{language}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-zinc-400 hover:text-zinc-200 transition-colors p-1 rounded hover:bg-zinc-800"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-emerald-400" />
              <span className="text-emerald-400 text-[10px]">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              <span className="text-[10px]">Copy</span>
            </>
          )}
        </button>
      </div>
      <pre
        className={cn(
          "p-3.5 text-xs font-mono-data text-zinc-300 overflow-auto whitespace-pre leading-relaxed",
          maxHeight
        )}
      >
        <code>{formattedCode}</code>
      </pre>
    </div>
  );
}
