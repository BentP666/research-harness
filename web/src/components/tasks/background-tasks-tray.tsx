"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronUp, X, Activity } from "lucide-react";
import { useBackgroundTasks, dismissTask } from "@/lib/tasks-store";
import { TaskProgress } from "./task-progress";
import { cn } from "@/lib/utils";

/**
 * Floating tray (bottom-right) showing active long-running tasks.
 *
 * Hidden when zero tasks. Collapsible to a single chip showing count.
 * Each task shows TaskProgress + dismiss button. Clicking a task with
 * an `href` navigates to the source page.
 */
export function BackgroundTasksTray() {
  const tasks = useBackgroundTasks();
  const [collapsed, setCollapsed] = useState(false);

  const running = useMemo(
    () => tasks.filter((t) => t.status === "running" || t.status === "queued"),
    [tasks],
  );

  if (tasks.length === 0) return null;

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-40 flex flex-col items-end gap-2 sm:bottom-6 sm:right-6">
      <AnimatePresence mode="popLayout">
        {!collapsed ? (
          <motion.div
            key="expanded"
            layout
            initial={{ opacity: 0, y: 12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.96 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="pointer-events-auto w-80 overflow-hidden rounded-2xl border border-white/60 bg-white/85 shadow-xl shadow-indigo-500/[0.08] backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/85"
          >
            {/* Header */}
            <div className="flex items-center gap-2 border-b border-slate-200/70 px-3 py-2 dark:border-slate-800">
              <div className="relative">
                <Activity className="size-3.5 text-indigo-500" />
                {running.length > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 size-1.5 animate-pulse rounded-full bg-indigo-500" />
                )}
              </div>
              <div className="flex-1 text-xs font-semibold tracking-tight">
                后台任务 · {running.length} 进行中
              </div>
              <button
                type="button"
                onClick={() => setCollapsed(true)}
                aria-label="折叠"
                className="rounded p-1 text-muted-foreground transition-colors hover:bg-slate-100 hover:text-foreground dark:hover:bg-slate-800"
              >
                <ChevronUp className="size-3.5 rotate-180" />
              </button>
            </div>

            {/* Task list */}
            <div className="max-h-80 overflow-y-auto p-2">
              <ul className="space-y-1">
                <AnimatePresence initial={false}>
                  {tasks.map((task) => (
                    <motion.li
                      key={task.id}
                      layout
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                    >
                      <div
                        className={cn(
                          "group/row relative rounded-lg px-2.5 py-2 transition-colors",
                          "hover:bg-slate-100/80 dark:hover:bg-slate-800/50",
                        )}
                      >
                        <div className="mb-1 flex items-center gap-2">
                          {task.href ? (
                            <Link
                              href={task.href}
                              className="flex-1 truncate text-xs font-medium hover:underline"
                            >
                              {task.title}
                            </Link>
                          ) : (
                            <div className="flex-1 truncate text-xs font-medium">
                              {task.title}
                            </div>
                          )}
                          <button
                            type="button"
                            onClick={() => dismissTask(task.id)}
                            aria-label="关闭"
                            className="rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:bg-slate-200 hover:text-foreground group-hover/row:opacity-100 dark:hover:bg-slate-700"
                          >
                            <X className="size-3" />
                          </button>
                        </div>
                        <TaskProgress task={task} compact />
                      </div>
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            </div>
          </motion.div>
        ) : (
          <motion.button
            key="collapsed"
            type="button"
            onClick={() => setCollapsed(false)}
            initial={{ opacity: 0, y: 8, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.9 }}
            className="pointer-events-auto inline-flex items-center gap-2 rounded-full border border-white/60 bg-white/90 px-3 py-1.5 text-xs font-medium shadow-lg shadow-indigo-500/10 backdrop-blur-xl transition-transform hover:-translate-y-0.5 dark:border-white/10 dark:bg-slate-900/90"
          >
            <div className="relative">
              <Activity className="size-3.5 text-indigo-500" />
              {running.length > 0 && (
                <span className="absolute -right-0.5 -top-0.5 size-1.5 animate-pulse rounded-full bg-indigo-500" />
              )}
            </div>
            <span>后台任务 · {tasks.length}</span>
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
