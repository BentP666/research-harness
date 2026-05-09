"use client";

import { motion } from "framer-motion";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";
import type { BackgroundTask } from "@/lib/tasks-store";
import { cn } from "@/lib/utils";

/**
 * Inline progress indicator for long-running operations.
 *
 * Renders three layers:
 * 1. Determinate bar when `progress` is set (0..1)
 * 2. Indeterminate shimmer bar when `progress` is null
 * 3. Phase + step counter as caption text
 *
 * Use as a drop-in replacement for spinner-only feedback.
 */
export function TaskProgress({
  task,
  compact = false,
}: {
  task: BackgroundTask;
  compact?: boolean;
}) {
  const isRunning = task.status === "running" || task.status === "queued";
  const isDone = task.status === "succeeded";
  const isFail = task.status === "failed" || task.status === "cancelled";

  const pct =
    task.progress != null
      ? Math.max(0, Math.min(1, task.progress)) * 100
      : null;

  return (
    <div className={cn("w-full", compact ? "space-y-1.5" : "space-y-2")}>
      <div className="flex items-center gap-2">
        {isRunning && (
          <Loader2 className="size-3.5 shrink-0 animate-spin text-indigo-500" />
        )}
        {isDone && (
          <CheckCircle2 className="size-3.5 shrink-0 text-emerald-500" />
        )}
        {isFail && <XCircle className="size-3.5 shrink-0 text-rose-500" />}
        <span className="flex-1 truncate text-xs font-medium text-foreground">
          {task.phase ?? task.title}
        </span>
        {task.step ? (
          <span className="text-[11px] tabular-nums text-muted-foreground">
            {task.step.current}/{task.step.total}
          </span>
        ) : pct != null ? (
          <span className="text-[11px] tabular-nums text-muted-foreground">
            {Math.round(pct)}%
          </span>
        ) : null}
      </div>

      {/* Progress bar — determinate or shimmer */}
      <div
        className="relative h-1 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct ?? undefined}
      >
        {pct != null ? (
          <motion.div
            className={cn(
              "absolute inset-y-0 left-0 rounded-full",
              isFail
                ? "bg-gradient-to-r from-rose-400 to-rose-500"
                : isDone
                  ? "bg-gradient-to-r from-emerald-400 to-emerald-500"
                  : "bg-gradient-to-r from-indigo-400 via-violet-500 to-fuchsia-500",
            )}
            initial={false}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          />
        ) : isRunning ? (
          <motion.div
            className="absolute inset-y-0 w-1/3 rounded-full bg-gradient-to-r from-transparent via-indigo-500 to-transparent"
            animate={{ x: ["-50%", "200%"] }}
            transition={{
              duration: 1.6,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
        ) : null}
      </div>

      {task.subtitle && !compact && (
        <p className="truncate text-[11px] text-muted-foreground">
          {task.subtitle}
        </p>
      )}
      {isFail && task.error && (
        <p className="truncate text-[11px] text-rose-500">{task.error}</p>
      )}
    </div>
  );
}
