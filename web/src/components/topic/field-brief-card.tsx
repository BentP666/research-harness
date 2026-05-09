"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Database,
  Target,
  PenLine,
  CircleHelp,
  Cpu,
  CalendarDays,
  RefreshCw,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { fetchFieldBrief, rebuildFieldBrief } from "@/lib/api";
import type { FieldBrief, FieldBriefResponse } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n-provider";
import { RetrievalTriggerButton } from "@/components/topic/retrieval-trigger-button";

interface Props {
  topicId: number;
}

type TileKey = "datasets" | "baselines" | "narrative_patterns" | "open_challenges" | "compute_bands" | "venue_options";

const TILES: { key: TileKey; icon: typeof Database; labelKey: string; abbr: string }[] = [
  { key: "datasets", icon: Database, labelKey: "fieldBrief.datasets", abbr: "DS" },
  { key: "baselines", icon: Target, labelKey: "fieldBrief.baselines", abbr: "BL" },
  { key: "narrative_patterns", icon: PenLine, labelKey: "fieldBrief.narratives", abbr: "NP" },
  { key: "open_challenges", icon: CircleHelp, labelKey: "fieldBrief.challenges", abbr: "CH" },
  { key: "compute_bands", icon: Cpu, labelKey: "fieldBrief.compute", abbr: "CB" },
  { key: "venue_options", icon: CalendarDays, labelKey: "fieldBrief.venues", abbr: "VO" },
];

function SaturationBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score < 0.33 ? "bg-blue-500" : score < 0.66 ? "bg-yellow-500" : "bg-red-500";
  const textColor = score < 0.33 ? "text-blue-700" : score < 0.66 ? "text-yellow-700" : "text-red-700";
  const label = score < 0.33 ? "Blue ocean" : score < 0.66 ? "Yellow zone" : "Red ocean";

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted-foreground">Saturation:</span>
      <div className="h-2.5 flex-1 rounded-full bg-slate-200 dark:bg-slate-700">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-medium ${textColor}`}>
        {score.toFixed(2)} ({label})
      </span>
    </div>
  );
}

function TileDetail({ tileKey, brief }: { tileKey: TileKey; brief: FieldBrief }) {
  const items = brief[tileKey];
  if (!Array.isArray(items) || items.length === 0) {
    return <p className="text-xs text-muted-foreground">No data</p>;
  }

  if (tileKey === "datasets") {
    return (
      <ul className="space-y-1">
        {(items as FieldBrief["datasets"]).map((d, i) => (
          <li key={i} className="text-xs">
            <span className="font-medium">{d.name}</span>
            {d.size && <span className="text-muted-foreground"> · {d.size}</span>}
            {d.gpu_req && <Badge variant="outline" className="ml-1 text-[10px]">{d.gpu_req}</Badge>}
          </li>
        ))}
      </ul>
    );
  }
  if (tileKey === "baselines") {
    return (
      <ul className="space-y-1">
        {(items as FieldBrief["baselines"]).map((b, i) => (
          <li key={i} className="text-xs">
            <span className="font-medium">{b.name}</span>
            <span className="text-muted-foreground"> · {b.metric_name}: {b.metric_value}</span>
          </li>
        ))}
      </ul>
    );
  }
  if (tileKey === "open_challenges") {
    return (
      <ul className="space-y-1">
        {(items as FieldBrief["open_challenges"]).map((c, i) => (
          <li key={i} className="text-xs">
            <span className="font-medium">{c.problem}</span>
            <Badge variant="outline" className="ml-1 text-[10px]">{c.maturity}</Badge>
          </li>
        ))}
      </ul>
    );
  }
  if (tileKey === "venue_options") {
    return (
      <ul className="space-y-1">
        {(items as FieldBrief["venue_options"]).map((v, i) => (
          <li key={i} className="text-xs">
            <span className="font-medium">{v.name}</span>
            {v.deadline && <span className="text-muted-foreground"> · deadline: {v.deadline}</span>}
            {v.acceptance_rate != null && <span className="text-muted-foreground"> · {(v.acceptance_rate * 100).toFixed(0)}%</span>}
          </li>
        ))}
      </ul>
    );
  }
  // narrative_patterns, compute_bands — string arrays
  return (
    <ul className="space-y-1">
      {(items as string[]).map((s, i) => (
        <li key={i} className="text-xs">{s}</li>
      ))}
    </ul>
  );
}

export default function FieldBriefCard({ topicId }: Props) {
  const { t } = useT();
  const qc = useQueryClient();
  const [expandedTile, setExpandedTile] = useState<TileKey | null>(null);

  const query = useQuery({
    queryKey: ["field-brief", topicId],
    queryFn: () => fetchFieldBrief(topicId),
  });

  const buildMut = useMutation({
    mutationFn: () => rebuildFieldBrief(topicId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["field-brief", topicId] });
    },
  });

  const data: FieldBriefResponse | null | undefined = query.data;

  // Loading state
  if (query.isLoading) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">{t("fieldBrief.title")}</CardTitle>
          <RetrievalTriggerButton topicId={topicId} stage="build" />
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            {t("fieldBrief.loading")}
          </div>
          <div className="mt-4 grid grid-cols-6 gap-2">
            {TILES.map((tile) => (
              <div key={tile.key} className="h-16 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (query.isError) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">{t("fieldBrief.title")}</CardTitle>
          <RetrievalTriggerButton topicId={topicId} stage="build" />
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 rounded-md bg-red-50 p-3 text-sm text-red-600 dark:bg-red-950 dark:text-red-400">
            <AlertCircle className="size-4" />
            {t("fieldBrief.error")}
          </div>
          <button
            onClick={() => query.refetch()}
            className="mt-2 rounded-md border px-3 py-1.5 text-xs hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            {t("fieldBrief.retry")}
          </button>
        </CardContent>
      </Card>
    );
  }

  // Empty state
  if (!data) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">{t("fieldBrief.title")}</CardTitle>
          <RetrievalTriggerButton topicId={topicId} stage="build" />
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-3 py-8">
          <Database className="size-12 text-slate-300" />
          <p className="text-sm text-muted-foreground">{t("fieldBrief.empty")}</p>
          <button
            onClick={() => buildMut.mutate()}
            disabled={buildMut.isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {buildMut.isPending ? t("fieldBrief.building") : t("fieldBrief.generate")}
          </button>
          {buildMut.isError && (
            <p className="text-xs text-red-500">{(buildMut.error as Error).message}</p>
          )}
        </CardContent>
      </Card>
    );
  }

  // Success state
  const { brief, meta } = data;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">{t("fieldBrief.title")}</CardTitle>
        <div className="flex items-center gap-2">
          {meta.stale && (
            <Badge variant="outline" className="border-orange-300 bg-orange-50 text-orange-700 text-xs dark:bg-orange-950 dark:text-orange-300">
              {t("fieldBrief.stale")}
            </Badge>
          )}
          <button
            onClick={() => buildMut.mutate()}
            disabled={buildMut.isPending}
            className="rounded-md border p-1.5 text-xs hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50"
            title={t("fieldBrief.refresh")}
          >
            <RefreshCw className={`size-3.5 ${buildMut.isPending ? "animate-spin" : ""}`} />
          </button>
          <RetrievalTriggerButton topicId={topicId} stage="build" />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <SaturationBar score={brief.saturation_score} />

        <div className="grid grid-cols-3 gap-2 md:grid-cols-6">
          {TILES.map((tile) => {
            const count = Array.isArray(brief[tile.key]) ? (brief[tile.key] as unknown[]).length : 0;
            const Icon = tile.icon;
            const isExpanded = expandedTile === tile.key;
            return (
              <button
                key={tile.key}
                onClick={() => setExpandedTile(isExpanded ? null : tile.key)}
                className={`flex flex-col items-center gap-1 rounded-lg border p-3 transition-colors ${
                  isExpanded
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-950"
                    : "hover:bg-slate-50 dark:hover:bg-slate-800"
                }`}
              >
                <Icon className="size-4 text-muted-foreground" />
                <span className="text-lg font-semibold">{count}</span>
                <span className="text-[10px] text-muted-foreground">{tile.abbr}</span>
              </button>
            );
          })}
        </div>

        {expandedTile && (
          <div className="rounded-lg border bg-slate-50 p-3 dark:bg-slate-900">
            <TileDetail tileKey={expandedTile} brief={brief} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
