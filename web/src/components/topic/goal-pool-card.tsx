"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Target, RefreshCw, AlertCircle, Loader2, ArrowUp, ArrowDown, Ban,
} from "lucide-react";
import { fetchGoals, buildGoalPool, updateGoal, deleteGoal } from "@/lib/api";
import type { Goal } from "@/lib/api";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { useT } from "@/lib/i18n-provider";

interface Props {
  topicId: number;
}

function ScoreBreakdownTooltip({ goal }: { goal: Goal }) {
  const bd = goal.scoring_breakdown;
  const items = [
    { label: "Headroom", value: bd.headroom },
    { label: "Feasibility", value: bd.feasibility },
    { label: "Evidence", value: bd.evidence_coverage },
    { label: "Venue Fit", value: bd.venue_fit },
    { label: "Compute Fit", value: bd.compute_fit },
  ];
  return (
    <div className="absolute right-0 top-full z-10 mt-1 w-64 rounded-lg border bg-white p-3 shadow-lg dark:bg-slate-900">
      <p className="mb-2 text-xs font-semibold">Score Breakdown</p>
      <div className="space-y-1.5">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-2">
            <span className="w-20 text-[10px] text-muted-foreground">{item.label}</span>
            <div className="h-1.5 flex-1 rounded-full bg-slate-200 dark:bg-slate-700">
              <div
                className="h-full rounded-full bg-blue-500"
                style={{ width: `${item.value * 100}%` }}
              />
            </div>
            <span className="w-8 text-right text-[10px] font-mono">{item.value.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function GoalPoolCard({ topicId }: Props) {
  const { t } = useT();
  const qc = useQueryClient();
  const [hoveredGoalId, setHoveredGoalId] = useState<number | null>(null);

  const query = useQuery({
    queryKey: ["goals", topicId],
    queryFn: () => fetchGoals(topicId),
  });

  const buildMut = useMutation({
    mutationFn: () => buildGoalPool(topicId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["goals", topicId] }),
  });

  const updateMut = useMutation({
    mutationFn: (vars: { goalId: number; body: { status?: string; priority_rank?: number } }) =>
      updateGoal(topicId, vars.goalId, vars.body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["goals", topicId] }),
  });

  const deleteMut = useMutation({
    mutationFn: (goalId: number) => deleteGoal(topicId, goalId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["goals", topicId] }),
  });

  // Loading
  if (query.isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">{t("goalPool.title")}</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            {t("goalPool.loading")}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error
  if (query.isError) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">{t("goalPool.title")}</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 rounded-md bg-red-50 p-3 text-sm text-red-600 dark:bg-red-950 dark:text-red-400">
            <AlertCircle className="size-4" />
            {t("goalPool.error")}
          </div>
        </CardContent>
      </Card>
    );
  }

  const goals = query.data ?? [];

  // Empty
  if (goals.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">{t("goalPool.title")}</CardTitle></CardHeader>
        <CardContent className="flex flex-col items-center gap-3 py-8">
          <Target className="size-12 text-slate-300" />
          <p className="text-sm text-muted-foreground">{t("goalPool.empty")}</p>
          {buildMut.isError && (
            <div className="space-y-2 text-center">
              <p className="text-xs text-red-500">{(buildMut.error as Error).message}</p>
              {(buildMut.error as Error).message.toLowerCase().includes("field brief") && (
                <p className="text-xs text-muted-foreground">{t("goalPool.emptyHint")}</p>
              )}
            </div>
          )}
          <button
            onClick={() => buildMut.mutate()}
            disabled={buildMut.isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {buildMut.isPending ? t("goalPool.building") : t("goalPool.build")}
          </button>
        </CardContent>
      </Card>
    );
  }

  // Success
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">{t("goalPool.title")}</CardTitle>
        <button
          onClick={() => buildMut.mutate()}
          disabled={buildMut.isPending}
          className="flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50"
        >
          <RefreshCw className={`size-3.5 ${buildMut.isPending ? "animate-spin" : ""}`} />
          {t("goalPool.rebuild")}
        </button>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b text-xs text-muted-foreground">
              <tr>
                <th className="px-2 py-2 text-left">#</th>
                <th className="px-2 py-2 text-left">{t("goalPool.dataset")}</th>
                <th className="px-2 py-2 text-left">{t("goalPool.baseline")}</th>
                <th className="px-2 py-2 text-left">{t("goalPool.delta")}</th>
                <th className="px-2 py-2 text-left">{t("goalPool.venue")}</th>
                <th className="px-2 py-2 text-left">{t("goalPool.score")}</th>
                <th className="px-2 py-2 text-right">{t("goalPool.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {goals.map((goal) => {
                const isActive = goal.status === "active" && goal.priority_rank === 1;
                return (
                  <tr
                    key={goal.id}
                    className={`border-b transition-colors ${
                      isActive
                        ? "border-l-4 border-l-blue-600 bg-blue-50 dark:bg-blue-950"
                        : ""
                    }`}
                  >
                    <td className="px-2 py-2 font-mono">{goal.priority_rank}</td>
                    <td className="px-2 py-2">{goal.dataset}</td>
                    <td className="px-2 py-2">{goal.baseline}</td>
                    <td className="px-2 py-2 font-mono text-xs">
                      {goal.target_metric_delta > 0 ? "-" : "+"}
                      {Math.abs(goal.target_metric_delta).toFixed(1)} {goal.metric_name}
                    </td>
                    <td className="px-2 py-2 text-xs">{goal.target_venue || "—"}</td>
                    <td
                      className="relative px-2 py-2 font-mono"
                      onMouseEnter={() => setHoveredGoalId(goal.id)}
                      onMouseLeave={() => setHoveredGoalId(null)}
                    >
                      <span className="cursor-help underline decoration-dotted">
                        {goal.score.toFixed(2)}
                      </span>
                      {hoveredGoalId === goal.id && (
                        <ScoreBreakdownTooltip goal={goal} />
                      )}
                    </td>
                    <td className="px-2 py-2">
                      <div className="flex justify-end gap-1">
                        <button
                          onClick={() => updateMut.mutate({ goalId: goal.id, body: { priority_rank: Math.max(1, goal.priority_rank - 1) } })}
                          disabled={goal.priority_rank === 1}
                          className="rounded p-1 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800"
                          title={t("goalPool.moveUp")}
                        >
                          <ArrowUp className="size-3" />
                        </button>
                        <button
                          onClick={() => updateMut.mutate({ goalId: goal.id, body: { priority_rank: goal.priority_rank + 1 } })}
                          className="rounded p-1 hover:bg-slate-100 dark:hover:bg-slate-800"
                          title={t("goalPool.moveDown")}
                        >
                          <ArrowDown className="size-3" />
                        </button>
                        <button
                          onClick={() => deleteMut.mutate(goal.id)}
                          className="rounded p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-950"
                          title={t("goalPool.skip")}
                        >
                          <Ban className="size-3" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
