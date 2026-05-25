"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  GitBranch,
  PauseCircle,
  PlayCircle,
  ShieldCheck,
} from "lucide-react";
import {
  decideLongTaskGate,
  fetchLongTaskRun,
  fetchLongTaskRuns,
  superviseLongTaskRun,
  type LongTaskGate,
  type LongTaskTask,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

function statusTone(status: string): {
  icon: typeof CheckCircle2;
  className: string;
  badge: "default" | "secondary" | "destructive" | "outline";
} {
  if (status === "complete" || status === "approved") {
    return {
      icon: CheckCircle2,
      className: "text-emerald-600 bg-emerald-500/10 border-emerald-500/20",
      badge: "default",
    };
  }
  if (status === "quarantined" || status === "rejected") {
    return {
      icon: AlertTriangle,
      className: "text-red-600 bg-red-500/10 border-red-500/20",
      badge: "destructive",
    };
  }
  if (status === "waiting_gate" || status === "pending") {
    return {
      icon: ShieldCheck,
      className: "text-amber-600 bg-amber-500/10 border-amber-500/20",
      badge: "secondary",
    };
  }
  if (status === "running") {
    return {
      icon: PlayCircle,
      className: "text-blue-600 bg-blue-500/10 border-blue-500/20",
      badge: "secondary",
    };
  }
  if (status === "paused" || status === "blocked") {
    return {
      icon: PauseCircle,
      className: "text-slate-600 bg-slate-500/10 border-slate-500/20",
      badge: "outline",
    };
  }
  return {
    icon: Clock3,
    className: "text-slate-500 bg-slate-500/5 border-slate-500/10",
    badge: "outline",
  };
}

function ProgressStat({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-2xl border bg-card px-4 py-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
    </div>
  );
}

function TaskNode({ task, index }: { task: LongTaskTask; index: number }) {
  const tone = statusTone(task.status);
  const Icon = tone.icon;
  return (
    <div className="relative flex gap-3 pb-5 last:pb-0">
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "flex size-9 items-center justify-center rounded-full border",
            tone.className
          )}
        >
          <Icon className="size-4" />
        </div>
        <div className="mt-2 h-full min-h-6 w-px bg-border last:hidden" />
      </div>
      <Card className="flex-1">
        <CardHeader className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">
              {task.id || `N${index + 1}`}
            </span>
            <Badge variant={tone.badge}>{task.status}</Badge>
            {task.risk_level && task.risk_level !== "low" ? (
              <Badge variant="outline">risk: {task.risk_level}</Badge>
            ) : null}
          </div>
          <CardTitle className="text-base">{task.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {task.summary || "No summary yet. The worker has not reported a final result."}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function GateCard({ gate, runId }: { gate: LongTaskGate; runId: string }) {
  const [token, setToken] = useState("");
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (decision: "approved" | "rejected" | "paused" | "replan_requested") =>
      decideLongTaskGate(gate.id, {
        decision,
        actor: "mobile-ui",
        token,
        note:
          decision === "approved"
            ? "Approved from LongRun mobile UI"
            : `Decision from LongRun mobile UI: ${decision}`,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["longtask-run", runId] });
      await queryClient.invalidateQueries({ queryKey: ["longtask-runs"] });
    },
  });

  return (
    <Card className="border-amber-500/30 bg-amber-500/5">
      <CardHeader>
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-5 text-amber-600" />
          <Badge variant="secondary">{gate.status}</Badge>
        </div>
        <CardTitle className="text-lg">{gate.title}</CardTitle>
        <CardDescription>
          {gate.gate_type} · {gate.token_required ? "approval token required" : "no token required"}
        </CardDescription>
      </CardHeader>
      {gate.status === "pending" ? (
        <CardContent className="space-y-3">
          {gate.notification?.action_url ? (
            <div className="space-y-2 rounded-2xl border bg-background/80 p-3">
              <label className="block space-y-1 text-sm">
                <span className="font-medium">Signed confirmation link</span>
                <Input
                  aria-label="Signed confirmation link"
                  readOnly
                  value={gate.notification.action_url}
                />
              </label>
              <details className="text-sm">
                <summary className="cursor-pointer text-muted-foreground">
                  Copy notification payload
                </summary>
                <Textarea
                  aria-label="Notification payload"
                  className="mt-2 min-h-32 font-mono text-xs"
                  readOnly
                  value={JSON.stringify(gate.notification, null, 2)}
                />
              </details>
            </div>
          ) : null}
          {gate.token_required ? (
            <label className="block space-y-1 text-sm">
              <span className="font-medium">Approval token</span>
              <Input
                aria-label="Approval token"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                placeholder="Paste mobile approval token"
                type="password"
              />
            </label>
          ) : null}
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <Button onClick={() => mutation.mutate("approved")}>Approve</Button>
            <Button variant="outline" onClick={() => mutation.mutate("replan_requested")}>
              Replan
            </Button>
            <Button variant="outline" onClick={() => mutation.mutate("paused")}>
              Pause
            </Button>
            <Button variant="destructive" onClick={() => mutation.mutate("rejected")}>
              Reject
            </Button>
          </div>
          {mutation.isError ? (
            <p className="text-sm text-red-600">
              {(mutation.error as Error).message}
            </p>
          ) : null}
        </CardContent>
      ) : null}
    </Card>
  );
}

export default function LongRunPage() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const runsQuery = useQuery({
    queryKey: ["longtask-runs"],
    queryFn: fetchLongTaskRuns,
  });
  const runs = runsQuery.data ?? [];
  const activeRunId = selectedRunId ?? runs[0]?.id ?? null;

  const detailQuery = useQuery({
    queryKey: ["longtask-run", activeRunId],
    queryFn: () => fetchLongTaskRun(activeRunId!),
    enabled: Boolean(activeRunId),
  });
  const detail = detailQuery.data;
  const activeGates = detail?.gates.filter((gate) => gate.status === "pending") ?? [];
  const completed = detail?.tasks.filter((task) => task.status === "complete").length ?? 0;
  const total = detail?.tasks.length ?? 0;
  const queryClient = useQueryClient();
  const superviseMutation = useMutation({
    mutationFn: () =>
      superviseLongTaskRun(activeRunId!, {
        max_cycles: 3,
        execute: false,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["longtask-run", activeRunId] });
      await queryClient.invalidateQueries({ queryKey: ["longtask-runs"] });
    },
  });

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <section className="rounded-3xl border bg-gradient-to-br from-slate-950 to-slate-900 p-5 text-white shadow-xl sm:p-7">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-indigo-200">
              <GitBranch className="size-4" />
              Codex LongTask Supervisor
            </div>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">
            Mobile approvals for long-running Codex work.
          </h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-300">
              See the execution path, inspect each node summary, and approve the
              next critical gate from a phone-friendly control surface.
            </p>
          </div>
          <Badge variant="secondary" className="bg-white/10 text-white">
            1.0.0 · local-first
          </Badge>
        </div>
      </section>

      {runsQuery.isLoading ? (
        <Skeleton className="h-28 w-full" />
      ) : runs.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No longtask runs yet</CardTitle>
            <CardDescription>
              Start one with <code>rh longtask start objective.md</code>.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          <aside className="space-y-2">
            {runs.map((run) => (
              <button
                type="button"
                key={run.id}
                onClick={() => setSelectedRunId(run.id)}
                className={cn(
                  "w-full rounded-2xl border p-3 text-left transition hover:bg-muted",
                  activeRunId === run.id && "border-primary bg-primary/5"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="font-medium">{run.title}</div>
                  <Badge variant={statusTone(run.status).badge}>{run.status}</Badge>
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  {run.complete_count ?? 0}/{run.task_count ?? 0} complete ·{" "}
                  {run.pending_gate_count ?? 0} gates
                </div>
              </button>
            ))}
          </aside>

          <section className="space-y-4">
            {detailQuery.isLoading || !detail ? (
              <Skeleton className="h-72 w-full" />
            ) : (
              <>
                <div className="grid grid-cols-3 gap-3">
                  <ProgressStat label="Tasks" value={`${completed}/${total}`} />
                  <ProgressStat label="Gates" value={activeGates.length} />
                  <ProgressStat label="Workers" value={detail.run.max_workers} />
                </div>

                <Card>
                  <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="font-medium">Safe local push</div>
                      <p className="text-sm text-muted-foreground">
                        Run a dry supervision cycle from mobile. Real Codex
                        execution stays server/CLI controlled.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      disabled={superviseMutation.isPending || !activeRunId}
                      onClick={() => superviseMutation.mutate()}
                    >
                      {superviseMutation.isPending ? "Running…" : "Run safe cycle"}
                    </Button>
                  </CardContent>
                </Card>

                {activeGates.map((gate) => (
                  <GateCard key={gate.id} gate={gate} runId={detail.run.id} />
                ))}

                <Card>
                  <CardHeader>
                    <CardTitle>{detail.run.title}</CardTitle>
                    <CardDescription>
                      {detail.run.status} · {detail.run.id}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-0">
                      {detail.tasks.map((task, index) => (
                        <TaskNode key={task.id} task={task} index={index} />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
