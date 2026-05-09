"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Coins,
  Cpu,
  Layers,
  ArrowRight,
  FileClock,
  TrendingUp,
  Filter,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import { fetchLedger, fetchDailyUsage } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { RESEARCH_STAGES, STAGE_LABELS, type ResearchStage } from "@/lib/types";
import { useT } from "@/lib/i18n-provider";

// ---------------------------------------------------------------------------
// Color palette
// ---------------------------------------------------------------------------

const MODEL_COLORS = [
  "#6366f1", // indigo
  "#3b82f6", // blue
  "#f59e0b", // amber
  "#10b981", // emerald
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#06b6d4", // cyan
  "#f97316", // orange
];

const STAGE_CHART_COLORS: Record<ResearchStage, string> = {
  init: "#94a3b8",
  build: "#3b82f6",
  analyze: "#8b5cf6",
  propose: "#f59e0b",
  experiment: "#10b981",
  write: "#f43f5e",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(Math.round(n));
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function BudgetsPage() {
  const { t } = useT();

  const sinceMonth = new Date().toISOString().slice(0, 7) + "-01";

  const byAgentQ = useQuery({
    queryKey: ["ledger-by-agent", sinceMonth],
    queryFn: () => fetchLedger({ since: sinceMonth, group_by: "agent" }),
  });

  const byStageQ = useQuery({
    queryKey: ["ledger-by-stage", sinceMonth],
    queryFn: () => fetchLedger({ since: sinceMonth, group_by: "stage" }),
  });

  const dailyQ = useQuery({
    queryKey: ["usage-daily-30"],
    queryFn: () => fetchDailyUsage({ days: 30 }),
    refetchInterval: 30_000,
  });

  const recentQ = useQuery({
    queryKey: ["ledger-recent", sinceMonth],
    queryFn: () => fetchLedger({ since: sinceMonth }),
  });

  // -- Model pie data -------------------------------------------------------
  // Derive month-scoped totals from the same ledger source the by-model card
  // uses. Avoids the regression where the KPI showed all-time totals while
  // "by model" said "no usage this month".
  const modelRows = useMemo(
    () => (byAgentQ.data ?? []) as Array<Record<string, unknown>>,
    [byAgentQ.data]
  );
  const monthTotals = useMemo<{ prompt: number; completion: number }>(() => {
    return modelRows.reduce(
      (acc: { prompt: number; completion: number }, row) => {
        acc.prompt += Number(row.total_prompt) || 0;
        acc.completion += Number(row.total_completion) || 0;
        return acc;
      },
      { prompt: 0, completion: 0 },
    );
  }, [modelRows]);
  const prompt: number = monthTotals.prompt;
  const completion: number = monthTotals.completion;
  const totalTokens: number = prompt + completion;

  const pieData = useMemo(
    () =>
      modelRows.map((row, i) => {
        const name =
          (row.nickname as string) ?? (row.model as string) ?? "unknown";
        const promptT = Number(row.total_prompt) || 0;
        const completionT = Number(row.total_completion) || 0;
        const calls = Number(row.call_count) || 0;
        return {
          name,
          model: (row.model as string) ?? "",
          value: promptT + completionT,
          prompt: promptT,
          completion: completionT,
          calls,
          color: MODEL_COLORS[i % MODEL_COLORS.length],
        };
      }),
    [modelRows]
  );
  const modelTotal = pieData.reduce((s, r) => s + r.value, 0);

  // -- Stage bar data -------------------------------------------------------
  const stageRows = useMemo(
    () => (byStageQ.data ?? []) as Array<Record<string, unknown>>,
    [byStageQ.data]
  );
  const barData = useMemo(() => {
    const stageMap = new Map<string, { prompt: number; completion: number }>();
    for (const r of stageRows) {
      const stage = (r.stage as string) ?? "unknown";
      const prev = stageMap.get(stage) ?? { prompt: 0, completion: 0 };
      stageMap.set(stage, {
        prompt: prev.prompt + (Number(r.total_prompt) || 0),
        completion: prev.completion + (Number(r.total_completion) || 0),
      });
    }
    return RESEARCH_STAGES.map((stage) => {
      const vals = stageMap.get(stage) ?? { prompt: 0, completion: 0 };
      return {
        stage,
        label: STAGE_LABELS[stage],
        prompt: vals.prompt,
        completion: vals.completion,
        total: vals.prompt + vals.completion,
        fill: STAGE_CHART_COLORS[stage],
      };
    });
  }, [stageRows]);

  // -- Daily trend area data (server-aggregated) ----------------------------
  const recentRows = useMemo(
    () => (recentQ.data ?? []) as Array<Record<string, unknown>>,
    [recentQ.data]
  );
  const trendData = useMemo(() => {
    const rows = dailyQ.data ?? [];
    return rows.map((r) => ({
      day: r.day.slice(5),
      fullDay: r.day,
      prompt: r.prompt_tokens,
      completion: r.completion_tokens,
      total: r.prompt_tokens + r.completion_tokens,
    }));
  }, [dailyQ.data]);

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div>
        <h1 className="font-serif text-3xl font-medium tracking-tight">
          {t("budgets.title")}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("budgets.subtitle")}
        </p>
      </div>

      {/* Top: total tokens this month */}
      <Card>
        <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:gap-6">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 text-white">
            <Coins className="size-6" />
          </div>
          <div className="flex-1">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {t("tokens.thisMonth")}
            </p>
            <div className="mt-0.5 flex items-baseline gap-2 text-3xl font-semibold tabular-nums">
              {byAgentQ.isPending ? (
                <Skeleton className="h-8 w-24" />
              ) : (
                <span>{formatTokens(totalTokens)}</span>
              )}
              <span className="text-sm font-normal text-muted-foreground">
                {t("budgets.tokens")}
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {t("tokens.promptCompletionSplit", {
                prompt: formatTokens(prompt),
                completion: formatTokens(completion),
              })}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* By model — PieChart (donut) */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Cpu className="size-4" />
            <CardTitle className="text-sm">
              {t("budgets.byModelTitle")}
            </CardTitle>
          </div>
          <p className="text-xs text-muted-foreground">
            {t("budgets.byModelSubtitle")}
          </p>
        </CardHeader>
        <CardContent>
          {byAgentQ.isPending ? (
            <Skeleton className="h-48 w-full" />
          ) : pieData.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              {t("budgets.noUsage")}
            </p>
          ) : pieData.length === 1 ? (
            /* Single model — show summary card instead of a pie */
            <div className="rounded-lg border bg-card p-4">
              <div className="flex items-center gap-2">
                <span
                  className="inline-block size-3 rounded-full"
                  style={{ backgroundColor: pieData[0].color }}
                />
                <span className="font-medium text-sm">{pieData[0].name}</span>
                {pieData[0].model && (
                  <Badge
                    variant="secondary"
                    className="h-4 text-[10px] px-1.5"
                  >
                    {pieData[0].model}
                  </Badge>
                )}
              </div>
              <div className="mt-2 flex items-baseline gap-3">
                <span className="text-2xl font-semibold tabular-nums">
                  {formatTokens(pieData[0].value)}
                </span>
                <span className="text-xs text-muted-foreground">
                  {pieData[0].calls} {t("budgets.calls")}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                {formatTokens(pieData[0].prompt)} {t("budgets.promptTokens")}{" "}
                · {formatTokens(pieData[0].completion)}{" "}
                {t("budgets.completionTokens")}
              </p>
            </div>
          ) : (
            /* Multiple models — donut chart + legend */
            <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
              <div className="h-52 w-52 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius="55%"
                      outerRadius="85%"
                      paddingAngle={2}
                      stroke="none"
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const d = payload[0].payload as (typeof pieData)[0];
                        const pct =
                          modelTotal > 0
                            ? ((d.value / modelTotal) * 100).toFixed(1)
                            : "0";
                        return (
                          <div className="rounded-md border bg-background p-2 text-xs shadow-lg">
                            <div className="font-medium">{d.name}</div>
                            <div>
                              {formatTokens(d.value)} {t("budgets.tokens")} (
                              {pct}%)
                            </div>
                            <div className="text-muted-foreground">
                              {d.calls} {t("budgets.calls")}
                            </div>
                          </div>
                        );
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Legend list */}
              <div className="flex-1 space-y-2 min-w-0">
                {pieData.map((entry, i) => {
                  const pct =
                    modelTotal > 0
                      ? ((entry.value / modelTotal) * 100).toFixed(0)
                      : "0";
                  return (
                    <div
                      key={i}
                      className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2 transition-colors hover:bg-muted/30"
                    >
                      <span
                        className="inline-block size-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: entry.color }}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium">
                            {entry.name}
                          </span>
                          {entry.model && (
                            <Badge
                              variant="secondary"
                              className="h-4 text-[10px] px-1.5"
                            >
                              {entry.model}
                            </Badge>
                          )}
                        </div>
                        <p className="text-[11px] text-muted-foreground">
                          {formatTokens(entry.prompt)}{" "}
                          {t("budgets.promptTokens")} ·{" "}
                          {formatTokens(entry.completion)}{" "}
                          {t("budgets.completionTokens")}
                        </p>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-sm font-semibold tabular-nums">
                          {formatTokens(entry.value)}
                        </div>
                        <div className="text-[11px] text-muted-foreground tabular-nums">
                          {pct}% · {entry.calls} {t("budgets.calls")}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* By stage — BarChart */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Layers className="size-4" />
            <CardTitle className="text-sm">
              {t("budgets.byStageTitle")}
            </CardTitle>
          </div>
          <p className="text-xs text-muted-foreground">
            {t("budgets.byStageSubtitle")}
          </p>
        </CardHeader>
        <CardContent>
          {byStageQ.isPending ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} barCategoryGap="20%">
                  <CartesianGrid
                    strokeDasharray="3 3"
                    opacity={0.3}
                    vertical={false}
                  />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v: number) => formatTokens(v)}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload as (typeof barData)[0];
                      return (
                        <div className="rounded-md border bg-background p-2 text-xs shadow-lg">
                          <div className="font-medium">{d.label}</div>
                          <div>
                            {t("budgets.totalTokens")}:{" "}
                            {formatTokens(d.total)}
                          </div>
                          <div className="text-muted-foreground">
                            {formatTokens(d.prompt)}{" "}
                            {t("budgets.promptTokens")} ·{" "}
                            {formatTokens(d.completion)}{" "}
                            {t("budgets.completionTokens")}
                          </div>
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="prompt" stackId="a" radius={[0, 0, 0, 0]}>
                    {barData.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={entry.fill}
                        fillOpacity={0.6}
                      />
                    ))}
                  </Bar>
                  <Bar dataKey="completion" stackId="a" radius={[4, 4, 0, 0]}>
                    {barData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                  <Legend
                    content={() => (
                      <div className="mt-2 flex items-center justify-center gap-4 text-[11px]">
                        <span className="flex items-center gap-1">
                          <span className="inline-block size-2.5 rounded-sm" style={{ backgroundColor: "#6366f1" }} />
                          {t("budgets.promptTokens")}
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="inline-block size-2.5 rounded-sm" style={{ backgroundColor: "#3b82f6" }} />
                          {t("budgets.completionTokens")}
                        </span>
                      </div>
                    )}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Daily trend — AreaChart */}
      {trendData.length > 1 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <TrendingUp className="size-4" />
              <CardTitle className="text-sm">
                {t("budgets.trendTitle")}
              </CardTitle>
            </div>
            <p className="text-xs text-muted-foreground">
              {t("budgets.trendSubtitle")}
            </p>
          </CardHeader>
          <CardContent>
            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData}>
                  <defs>
                    <linearGradient
                      id="gradPrompt"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="5%"
                        stopColor="#6366f1"
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="95%"
                        stopColor="#6366f1"
                        stopOpacity={0}
                      />
                    </linearGradient>
                    <linearGradient
                      id="gradCompletion"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="5%"
                        stopColor="#3b82f6"
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="95%"
                        stopColor="#3b82f6"
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    opacity={0.3}
                    vertical={false}
                  />
                  <XAxis
                    dataKey="day"
                    tick={{ fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v: number) => formatTokens(v)}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload as (typeof trendData)[0];
                      return (
                        <div className="rounded-md border bg-background p-2 text-xs shadow-lg">
                          <div className="font-medium">{d.fullDay}</div>
                          <div className="flex items-center gap-1.5">
                            <span
                              className="inline-block size-2 rounded-full"
                              style={{ backgroundColor: "#6366f1" }}
                            />
                            {t("budgets.promptTokens")}:{" "}
                            {formatTokens(d.prompt)}
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span
                              className="inline-block size-2 rounded-full"
                              style={{ backgroundColor: "#3b82f6" }}
                            />
                            {t("budgets.completionTokens")}:{" "}
                            {formatTokens(d.completion)}
                          </div>
                          <div className="mt-1 font-medium">
                            {t("budgets.totalTokens")}:{" "}
                            {formatTokens(d.total)}
                          </div>
                        </div>
                      );
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="prompt"
                    stackId="1"
                    stroke="#6366f1"
                    fill="url(#gradPrompt)"
                    strokeWidth={2}
                    name={t("budgets.promptTokens")}
                  />
                  <Area
                    type="monotone"
                    dataKey="completion"
                    stackId="1"
                    stroke="#3b82f6"
                    fill="url(#gradCompletion)"
                    strokeWidth={2}
                    name={t("budgets.completionTokens")}
                  />
                  <Legend
                    content={() => (
                      <div className="mt-2 flex items-center justify-center gap-4 text-[11px]">
                        <span className="flex items-center gap-1">
                          <span className="inline-block size-2.5 rounded-sm" style={{ backgroundColor: "#6366f1" }} />
                          {t("budgets.promptTokens")}
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="inline-block size-2.5 rounded-sm" style={{ backgroundColor: "#3b82f6" }} />
                          {t("budgets.completionTokens")}
                        </span>
                      </div>
                    )}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent activity */}
      <RecentActivityCard rows={recentRows} loading={recentQ.isPending} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Recent activity with per-model + per-stage filter
// ---------------------------------------------------------------------------

function RecentActivityCard({
  rows,
  loading,
}: {
  rows: Array<Record<string, unknown>>;
  loading: boolean;
}) {
  const { t } = useT();
  const [modelFilter, setModelFilter] = useState<string>("__all__");
  const [stageFilter, setStageFilter] = useState<string>("__all__");

  const modelOptions = useMemo(() => {
    const set = new Set<string>();
    for (const r of rows) {
      const m =
        (r.agent_name as string) ??
        (r.agent_model as string) ??
        "";
      if (m) set.add(m);
    }
    return Array.from(set).sort();
  }, [rows]);

  const filtered = useMemo(
    () =>
      rows.filter((r) => {
        const model =
          (r.agent_name as string) ?? (r.agent_model as string) ?? "";
        const stage = (r.stage as string) ?? "";
        if (modelFilter !== "__all__" && model !== modelFilter) return false;
        if (stageFilter !== "__all__" && stage !== stageFilter) return false;
        return true;
      }),
    [rows, modelFilter, stageFilter]
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <FileClock className="size-4" />
            <CardTitle className="text-sm">
              {t("budgets.recentTitle")}
            </CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Filter className="size-3 text-muted-foreground" />
            <select
              value={modelFilter}
              onChange={(e) => setModelFilter(e.target.value)}
              className="h-7 rounded-md border border-input bg-transparent px-2 text-xs"
            >
              <option value="__all__">
                {t("budgets.filters.allModels") || "All models"}
              </option>
              {modelOptions.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              className="h-7 rounded-md border border-input bg-transparent px-2 text-xs"
            >
              <option value="__all__">
                {t("budgets.filters.allStages") || "All stages"}
              </option>
              {RESEARCH_STAGES.map((s) => (
                <option key={s} value={s}>
                  {STAGE_LABELS[s]}
                </option>
              ))}
            </select>
            <Link
              href="/agents/ledger"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              {t("common.viewAll")}
              <ArrowRight className="size-3" />
            </Link>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-24 w-full" />
        ) : filtered.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            {rows.length === 0
              ? t("budgets.noUsage")
              : t("budgets.filters.noMatches") ||
                "No activity matches the current filter."}
          </p>
        ) : (
          <ul className="divide-y">
            {filtered.slice(0, 8).map((row, i) => {
              const ts = String(row.ts ?? "").slice(0, 16);
              const stage = (row.stage as string) ?? "\u2014";
              const model =
                (row.agent_name as string) ??
                (row.agent_model as string) ??
                "\u2014";
              const tok =
                (Number(row.prompt_tokens) || 0) +
                (Number(row.completion_tokens) || 0);
              return (
                <li
                  key={i}
                  className="flex items-center justify-between gap-2 py-1.5 text-xs"
                >
                  <span className="w-28 shrink-0 tabular-nums text-muted-foreground">
                    {ts.replace("T", " ")}
                  </span>
                  <Badge
                    variant="outline"
                    className="h-4 shrink-0 text-[10px] px-1.5 capitalize"
                  >
                    {stage}
                  </Badge>
                  <span className="truncate flex-1">{model}</span>
                  <span className="shrink-0 tabular-nums font-medium">
                    {formatTokens(tok)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
