/**
 * Formatting utilities for timestamps, durations, hashes, and numbers.
 */

export function formatDate(
  isoString?: string | null,
  options?: { includeTime?: boolean; relative?: boolean }
): string {
  if (!isoString) return "—";
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return "—";

    if (options?.relative) {
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffSec = Math.floor(diffMs / 1000);
      if (diffSec < 5) return "just now";
      if (diffSec < 60) return `${diffSec}s ago`;
      const diffMin = Math.floor(diffSec / 60);
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffHr = Math.floor(diffMin / 60);
      if (diffHr < 24) return `${diffHr}h ago`;
      const diffDays = Math.floor(diffHr / 24);
      return `${diffDays}d ago`;
    }

    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: options?.includeTime !== false ? "2-digit" : undefined,
      minute: options?.includeTime !== false ? "2-digit" : undefined,
      second: options?.includeTime !== false ? "2-digit" : undefined,
      hour12: false,
    }).format(date);
  } catch {
    return isoString;
  }
}

export function formatDuration(ms?: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  const sec = (ms / 1000).toFixed(1);
  if (ms < 60000) return `${sec}s`;
  const min = Math.floor(ms / 60000);
  const remSec = ((ms % 60000) / 1000).toFixed(0);
  return `${min}m ${remSec}s`;
}

export function formatShortId(id?: string | null, length: number = 8): string {
  if (!id) return "—";
  if (id.length <= length) return id;
  return id.substring(0, length);
}

export function formatBytes(bytes?: number | null): string {
  if (bytes == null || isNaN(bytes)) return "—";
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
