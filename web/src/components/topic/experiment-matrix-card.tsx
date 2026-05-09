"use client";

import { Fragment } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, AlertCircle, Grid3x3, Play } from "lucide-react";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { useT } from "@/lib/i18n-provider";
import {
  fetchExperimentMatrix, buildExperimentMatrix, runMatrixProxy,
} from "@/lib/api";
import type { MatrixCell } from "@/lib/api";

interface Props {
  topicId: number;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-slate-100 dark:bg-slate-800",
  proxy_running: "bg-blue-100 animate-pulse dark:bg-blue-900",
  proxy_done: "bg-slate-200 dark:bg-slate-700",
  pruned: "bg-red-100 dark:bg-red-900",
  promoted: "bg-green-100 dark:bg-green-900",
};

export default function ExperimentMatrixCard({ topicId }: Props) {
  const { t } = useT();
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: ["experiment-matrix", topicId],
    queryFn: () => fetchExperimentMatrix(topicId),
  });

  const buildMut = useMutation({
    mutationFn: () => buildExperimentMatrix(topicId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["experiment-matrix", topicId] }),
  });

  const proxyMut = useMutation({
    mutationFn: (maxCells: number) => runMatrixProxy(topicId, maxCells),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["experiment-matrix", topicId] }),
  });

  if (query.isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">{t("matrix.title")}</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> {t("matrix.loading")}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (query.isError) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">{t("matrix.title")}</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 rounded-md bg-red-50 p-3 text-sm text-red-600 dark:bg-red-950 dark:text-red-400">
            <AlertCircle className="size-4" /> {t("matrix.error")}
          </div>
        </CardContent>
      </Card>
    );
  }

  const cells = query.data ?? [];

  if (cells.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">{t("matrix.title")}</CardTitle></CardHeader>
        <CardContent className="flex flex-col items-center gap-3 py-6">
          <Grid3x3 className="size-10 text-slate-300" />
          <p className="text-sm text-muted-foreground">{t("matrix.empty")}</p>
          <button
            onClick={() => buildMut.mutate()}
            disabled={buildMut.isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {buildMut.isPending ? t("matrix.building") : t("matrix.build")}
          </button>
          {buildMut.isError && (
            <p className="text-xs text-red-500">{(buildMut.error as Error).message}</p>
          )}
        </CardContent>
      </Card>
    );
  }

  const goalIds = [...new Set(cells.map((c) => c.goal_id))];
  const atomIds = [...new Set(cells.flatMap((c) => c.atom_combo))];
  const pendingCount = cells.filter((c) => c.status === "pending").length;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">
          {t("matrix.title")} ({cells.length} cells)
        </CardTitle>
        <div className="flex gap-2">
          <button
            onClick={() => buildMut.mutate()}
            disabled={buildMut.isPending}
            className="rounded-md border px-3 py-1.5 text-xs hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50"
          >
            {t("matrix.rebuild")}
          </button>
          {pendingCount > 0 && (
            <button
              onClick={() => proxyMut.mutate(20)}
              disabled={proxyMut.isPending}
              className="flex items-center gap-1 rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              <Play className="size-3" />
              {proxyMut.isPending
                ? t("matrix.running")
                : `${t("matrix.runProxy")} (${pendingCount})`}
            </button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-1.5" style={{ gridTemplateColumns: `auto repeat(${atomIds.length}, 1fr)` }}>
          {/* Header row */}
          <div className="text-[10px] text-muted-foreground" />
          {atomIds.map((aid) => (
            <div key={aid} className="text-center text-[10px] text-muted-foreground">
              A{aid}
            </div>
          ))}

          {/* Goal rows */}
          {goalIds.map((gid) => (
            <Fragment key={`row-${gid}`}>
              <div className="text-[10px] text-muted-foreground whitespace-nowrap pr-2">
                G{gid}
              </div>
              {atomIds.map((aid) => {
                const cell = cells.find(
                  (c) => c.goal_id === gid && c.atom_combo.includes(aid)
                );
                if (!cell) {
                  return <div key={`${gid}-${aid}`} className="h-8 rounded bg-slate-50 dark:bg-slate-900" />;
                }
                return (
                  <div
                    key={`${gid}-${aid}`}
                    className={`flex h-8 items-center justify-center rounded text-[10px] font-mono ${STATUS_COLORS[cell.status] || ""}`}
                    title={`${cell.status}: delta=${cell.delta_to_sota?.toFixed(2) ?? "—"}`}
                  >
                    {cell.delta_to_sota != null
                      ? cell.delta_to_sota.toFixed(1)
                      : cell.status === "proxy_running"
                        ? "..."
                        : "—"}
                  </div>
                );
              })}
            </Fragment>
          ))}
        </div>

        {/* Legend */}
        <div className="mt-3 flex flex-wrap gap-3 text-[10px]">
          <span className="flex items-center gap-1"><span className="size-2.5 rounded bg-green-200" /> promoted</span>
          <span className="flex items-center gap-1"><span className="size-2.5 rounded bg-red-200" /> pruned</span>
          <span className="flex items-center gap-1"><span className="size-2.5 animate-pulse rounded bg-blue-200" /> running</span>
          <span className="flex items-center gap-1"><span className="size-2.5 rounded bg-slate-200" /> pending</span>
        </div>
      </CardContent>
    </Card>
  );
}
