"use client";

/**
 * Lightweight global task store for long-running background operations
 * (refresh trends, paper ingest, stage execution, etc.).
 *
 * Why not zustand: we don't need it. A module-level Set + listener pattern
 * gives us pub/sub in 40 lines and React 18's useSyncExternalStore is a
 * perfect fit. No external deps.
 */

import { useSyncExternalStore } from "react";

export type TaskStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface BackgroundTask {
  id: string;
  /** Short label shown in the tray header. e.g. "刷新研究趋势" */
  title: string;
  /** Optional context line. e.g. topic name, 12 papers */
  subtitle?: string;
  /** Progress 0-1, or null if indeterminate. */
  progress: number | null;
  /** Current phase description. e.g. "聚类中…" */
  phase?: string;
  /** Step counter for multi-step tasks. e.g. 3/6 */
  step?: { current: number; total: number };
  status: TaskStatus;
  /** Optional href the user can jump to (e.g. dashboard, topic page). */
  href?: string;
  /** Optional error message on failed status. */
  error?: string;
  /** Unix ms when the task started. */
  startedAt: number;
  /** Unix ms when the task finished (only set for terminal status). */
  finishedAt?: number;
}

type Listener = () => void;

const tasks = new Map<string, BackgroundTask>();
const listeners = new Set<Listener>();

// Snapshot cache — must return a stable reference between mutations,
// otherwise useSyncExternalStore will spin in an infinite loop.
let cachedSnapshot: BackgroundTask[] = [];
function rebuildSnapshot(): void {
  cachedSnapshot = Array.from(tasks.values()).sort(
    (a, b) => b.startedAt - a.startedAt,
  );
}

function emit(): void {
  rebuildSnapshot();
  for (const fn of listeners) fn();
}

export function startTask(
  init: Omit<BackgroundTask, "status" | "startedAt"> &
    Partial<Pick<BackgroundTask, "status" | "startedAt">>,
): string {
  const next: BackgroundTask = {
    status: "running",
    startedAt: Date.now(),
    ...init,
  };
  tasks.set(next.id, next);
  emit();
  return next.id;
}

export function updateTask(
  id: string,
  patch: Partial<Omit<BackgroundTask, "id">>,
): void {
  const cur = tasks.get(id);
  if (!cur) return;
  const next: BackgroundTask = { ...cur, ...patch };
  tasks.set(id, next);
  emit();
}

export function completeTask(
  id: string,
  result: { status: Extract<TaskStatus, "succeeded" | "failed" | "cancelled">; error?: string },
): void {
  const cur = tasks.get(id);
  if (!cur) return;
  const next: BackgroundTask = {
    ...cur,
    status: result.status,
    error: result.error,
    finishedAt: Date.now(),
    progress: result.status === "succeeded" ? 1 : cur.progress,
  };
  tasks.set(id, next);
  emit();
  // Auto-dismiss successful tasks after 6s, failed after 12s
  const dismissAfter = result.status === "succeeded" ? 6000 : 12000;
  setTimeout(() => {
    tasks.delete(id);
    emit();
  }, dismissAfter);
}

export function dismissTask(id: string): void {
  if (tasks.delete(id)) emit();
}

function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

const SERVER_EMPTY: BackgroundTask[] = [];

function getSnapshot(): BackgroundTask[] {
  return cachedSnapshot;
}

function getServerSnapshot(): BackgroundTask[] {
  return SERVER_EMPTY;
}

export function useBackgroundTasks(): BackgroundTask[] {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
