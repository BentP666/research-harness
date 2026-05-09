"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Beaker,
  ChevronDown,
  ChevronRight,
  Loader2,
  Plus,
  Trophy,
  TrendingUp,
  TrendingDown,
  Clock,
  Coins,
  CircleAlert,
  CircleCheck,
  Ban,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n-provider";
import { RetrievalTriggerButton } from "@/components/topic/retrieval-trigger-button";
import {
  fetchTopicExperiments,
  fetchExperimentRuns,
  createTopicExperiment,
  type CreateExperimentRequest,
} from "@/lib/api";
import type { TopicExperiment, ExperimentRunRow } from "@/lib/types";

interface ExperimentLeaderboardCardProps {
  topicId: number;
}

export function ExperimentLeaderboardCard({
  topicId,
}: ExperimentLeaderboardCardProps) {
  const { t } = useT();
  const q = useQuery({
    queryKey: ["topic-experiments", topicId],
    queryFn: () => fetchTopicExperiments(topicId),
    staleTime: 15_000,
  });

  if (q.isLoading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Beaker className="h-4 w-4" />
            {t("experiments.title") || "Experiments"}
          </CardTitle>
        </CardHeader>
        <CardContent className="py-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            {t("experiments.loading") || "Loading experiments…"}
          </div>
        </CardContent>
      </Card>
    );
  }

  const experiments = q.data?.experiments ?? [];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-sm font-medium">
          <span className="flex items-center gap-2">
            <Beaker className="h-4 w-4" />
            {t("experiments.title") || "Experiments"}
            {experiments.length > 0 && (
              <Badge variant="outline" className="ml-1 px-1.5 py-0 text-[10px]">
                {experiments.length}
              </Badge>
            )}
          </span>
          <span className="flex items-center gap-1">
            <RetrievalTriggerButton topicId={topicId} stage="experiment" />
            <NewExperimentButton topicId={topicId} />
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 pb-4">
        {experiments.length === 0 ? (
          <p className="py-2 text-xs text-muted-foreground">
            {t("experiments.empty") ||
              "No experiments yet — click New experiment to start an autonomous loop."}
          </p>
        ) : (
          experiments.map((exp) => (
            <ExperimentRow key={exp.id} experiment={exp} />
          ))
        )}
      </CardContent>
    </Card>
  );
}

function NewExperimentButton({ topicId }: { topicId: number }) {
  const { t } = useT();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    task_description: "",
    primary_metric: "val_acc",
    direction: "max" as "max" | "min",
    max_iterations: 5,
    patience: 3,
    max_cost_usd: 0,
    mode: "agent" as "strict" | "agent",
    timeout_sec: 300,
    fixture_files_json: "",
  });

  const mutation = useMutation({
    mutationFn: (body: CreateExperimentRequest) =>
      createTopicExperiment(topicId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["topic-experiments", topicId] });
      setOpen(false);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    let fixtures: Record<string, string> = {};
    if (form.fixture_files_json.trim()) {
      try {
        fixtures = JSON.parse(form.fixture_files_json);
      } catch {
        fixtures = {};
      }
    }
    mutation.mutate({
      name: form.name || undefined,
      task_description: form.task_description,
      fixture_files: fixtures,
      primary_metric: form.primary_metric,
      direction: form.direction,
      mode: form.mode,
      timeout_sec: form.timeout_sec,
      max_iterations: form.max_iterations,
      max_cost_usd: form.max_cost_usd,
      patience: form.patience,
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm" variant="outline" className="h-7 gap-1 text-xs">
            <Plus className="h-3 w-3" />
            {t("experiments.new") || "New"}
          </Button>
        }
      />
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {t("experiments.newTitle") || "New experiment loop"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3 text-sm">
          <label className="block">
            <span className="mb-1 block text-xs font-medium">
              {t("experiments.form.name") || "Name"}
            </span>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. prompt-tune-v1"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium">
              {t("experiments.form.task") || "Task description"}
            </span>
            <Textarea
              required
              rows={3}
              value={form.task_description}
              onChange={(e) =>
                setForm({ ...form, task_description: e.target.value })
              }
              placeholder="Describe what the LLM should implement in main.py…"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block text-xs font-medium">
                {t("experiments.form.metric") || "Primary metric"}
              </span>
              <Input
                required
                value={form.primary_metric}
                onChange={(e) =>
                  setForm({ ...form, primary_metric: e.target.value })
                }
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium">
                {t("experiments.form.direction") || "Direction"}
              </span>
              <select
                value={form.direction}
                onChange={(e) =>
                  setForm({
                    ...form,
                    direction: e.target.value as "max" | "min",
                  })
                }
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
              >
                <option value="max">max</option>
                <option value="min">min</option>
              </select>
            </label>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <label className="block">
              <span className="mb-1 block text-xs font-medium">
                {t("experiments.form.maxIter") || "Max iterations"}
              </span>
              <Input
                type="number"
                min={1}
                value={form.max_iterations}
                onChange={(e) =>
                  setForm({
                    ...form,
                    max_iterations: Number(e.target.value) || 1,
                  })
                }
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium">
                {t("experiments.form.patience") || "Patience"}
              </span>
              <Input
                type="number"
                min={1}
                value={form.patience}
                onChange={(e) =>
                  setForm({ ...form, patience: Number(e.target.value) || 1 })
                }
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium">
                {t("experiments.form.budget") || "Max $ (0=∞)"}
              </span>
              <Input
                type="number"
                step="0.01"
                min={0}
                value={form.max_cost_usd}
                onChange={(e) =>
                  setForm({
                    ...form,
                    max_cost_usd: Number(e.target.value) || 0,
                  })
                }
              />
            </label>
          </div>
          <label className="block">
            <span className="mb-1 block text-xs font-medium">
              {t("experiments.form.fixtures") || "Fixture files (JSON)"}
            </span>
            <Textarea
              rows={3}
              value={form.fixture_files_json}
              onChange={(e) =>
                setForm({ ...form, fixture_files_json: e.target.value })
              }
              placeholder='{"scorer.py": "...", "eval.jsonl": "..."}'
              className="font-mono text-xs"
            />
          </label>
          {mutation.isError && (
            <p className="text-xs text-rose-600">
              {String(mutation.error)}
            </p>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={mutation.isPending}
            >
              {t("common.cancel") || "Cancel"}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending && (
                <Loader2 className="mr-1 h-3 w-3 animate-spin" />
              )}
              {t("experiments.form.submit") || "Launch loop"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ExperimentRow({ experiment }: { experiment: TopicExperiment }) {
  const { t } = useT();
  const [expanded, setExpanded] = useState(false);

  const best = experiment.best;
  const dirIcon =
    experiment.direction === "max" ? (
      <TrendingUp className="h-3 w-3" />
    ) : (
      <TrendingDown className="h-3 w-3" />
    );

  return (
    <div className="rounded-md border border-border/60 bg-card/60">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-muted/40"
      >
        {expanded ? (
          <ChevronDown className="mt-0.5 h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronRight className="mt-0.5 h-3.5 w-3.5 text-muted-foreground" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium">
              {experiment.name}
            </span>
            <StatusBadge status={experiment.status} />
            {experiment.stopped_reason && (
              <span className="text-[10px] text-muted-foreground">
                · {experiment.stopped_reason}
              </span>
            )}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-0.5">
              {dirIcon}
              {experiment.primary_metric || "—"}
            </span>
            {best && best.primary_metric_value !== null && (
              <span className="inline-flex items-center gap-1">
                <Trophy className="h-3 w-3 text-amber-500" />
                {best.primary_metric_value.toFixed(4)}
                <span className="opacity-70">
                  @ {t("experiments.iterationShort") || "it"}{best.iteration}
                </span>
              </span>
            )}
          </div>
        </div>
      </button>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <RunsTable experimentId={experiment.id} direction={experiment.direction} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function RunsTable({
  experimentId,
  direction,
}: {
  experimentId: number;
  direction: "max" | "min";
}) {
  const { t } = useT();
  const q = useQuery({
    queryKey: ["experiment-runs", experimentId],
    queryFn: () => fetchExperimentRuns(experimentId),
    staleTime: 10_000,
  });

  if (q.isLoading) {
    return (
      <div className="px-3 py-2 text-[11px] text-muted-foreground">
        <Loader2 className="mr-1 inline h-3 w-3 animate-spin" />
        {t("experiments.loadingRuns") || "Loading runs…"}
      </div>
    );
  }

  const runs = q.data?.runs ?? [];
  if (runs.length === 0) {
    return (
      <div className="px-3 py-2 text-[11px] text-muted-foreground">
        {t("experiments.noRuns") || "No iterations recorded yet."}
      </div>
    );
  }

  // Compute best value for highlighting.
  const valid = runs
    .map((r) => r.primary_metric_value)
    .filter((v): v is number => v !== null && !Number.isNaN(v));
  const bestValue = valid.length
    ? direction === "max"
      ? Math.max(...valid)
      : Math.min(...valid)
    : null;

  return (
    <div className="border-t border-border/40 px-3 py-2">
      <div className="grid grid-cols-[auto_1fr_auto_auto_auto] items-center gap-2 text-[10px] uppercase tracking-wide text-muted-foreground">
        <span>{t("experiments.col.iter") || "Iter"}</span>
        <span>{t("experiments.col.metric") || "Metric"}</span>
        <span className="text-right">{t("experiments.col.time") || "Time"}</span>
        <span className="text-right">{t("experiments.col.cost") || "Cost"}</span>
        <span>{t("experiments.col.status") || "Status"}</span>
      </div>
      <div className="mt-1 divide-y divide-border/30">
        {runs.map((r) => (
          <RunRow key={r.id} run={r} isBest={r.primary_metric_value === bestValue} />
        ))}
      </div>
    </div>
  );
}

function RunRow({ run, isBest }: { run: ExperimentRunRow; isBest: boolean }) {
  const metric =
    run.primary_metric_value === null
      ? "—"
      : run.primary_metric_value.toFixed(4);
  return (
    <div
      className={cn(
        "grid grid-cols-[auto_1fr_auto_auto_auto] items-center gap-2 py-1 text-[11px]",
        isBest && "bg-amber-50/60 dark:bg-amber-500/10"
      )}
    >
      <span className="tabular-nums">#{run.iteration}</span>
      <span className="flex items-center gap-1 font-medium tabular-nums">
        {isBest && <Trophy className="h-3 w-3 text-amber-500" />}
        {metric}
      </span>
      <span className="inline-flex items-center gap-0.5 text-right tabular-nums text-muted-foreground">
        <Clock className="h-3 w-3" />
        {run.elapsed_sec.toFixed(1)}s
      </span>
      <span className="inline-flex items-center gap-0.5 text-right tabular-nums text-muted-foreground">
        <Coins className="h-3 w-3" />
        ${run.cost_usd.toFixed(3)}
      </span>
      <StatusBadge status={run.status} compact />
    </div>
  );
}

function StatusBadge({
  status,
  compact,
}: {
  status: string;
  compact?: boolean;
}) {
  const tone: Record<string, { cls: string; icon: typeof CircleCheck }> = {
    completed: {
      cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
      icon: CircleCheck,
    },
    running: {
      cls: "bg-blue-500/15 text-blue-700 dark:text-blue-300",
      icon: Loader2,
    },
    failed: {
      cls: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
      icon: CircleAlert,
    },
    timeout: {
      cls: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
      icon: Clock,
    },
    invalid: {
      cls: "bg-slate-500/15 text-slate-700 dark:text-slate-300",
      icon: Ban,
    },
    stopped: {
      cls: "bg-slate-500/15 text-slate-700 dark:text-slate-300",
      icon: Ban,
    },
    pending: {
      cls: "bg-slate-500/15 text-slate-700 dark:text-slate-300",
      icon: Clock,
    },
  };
  const meta = tone[status] ?? tone.pending;
  const Icon = meta.icon;
  const spin = status === "running";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium",
        meta.cls,
        compact && "px-1 py-0"
      )}
    >
      <Icon className={cn("h-2.5 w-2.5", spin && "animate-spin")} />
      {status}
    </span>
  );
}
