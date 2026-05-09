"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Scale,
  RefreshCw,
  AlertTriangle,
  ChevronDown,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import {
  fetchCalibrations,
  runCalibration,
  fetchUserPreferences,
  updateUserPreferences,
} from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n-provider";

const STAGE_ORDER = [
  "init",
  "build",
  "analyze",
  "propose",
  "experiment",
  "write",
];
const TIER_ORDER = ["economy", "standard", "premium"];

const TIER_DESC_KEYS: Record<string, string> = {
  economy: "settings.scoring.tierDescEconomy",
  standard: "settings.scoring.tierDescStandard",
  premium: "settings.scoring.tierDescPremium",
};

export default function ScoringRulesPage() {
  const qc = useQueryClient();
  const { t } = useT();

  const calibrationsQ = useQuery({
    queryKey: ["calibrations"],
    queryFn: fetchCalibrations,
  });
  const prefsQ = useQuery({
    queryKey: ["user-preferences"],
    queryFn: fetchUserPreferences,
  });

  const calibrateAllMut = useMutation({
    mutationFn: () => runCalibration({}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calibrations"] }),
  });
  const toggleShadowMut = useMutation({
    mutationFn: (live: number) =>
      updateUserPreferences({ auto_rollback_live: live }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["user-preferences"] }),
  });

  const [showAdvanced, setShowAdvanced] = useState(false);

  const rows = calibrationsQ.data ?? [];
  const byKey = new Map(rows.map((r) => [`${r.stage}/${r.tier}`, r]));
  const liveMode = prefsQ.data?.auto_rollback_live === 1;

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <div className="space-y-2">
        <Link
          href="/settings"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-3.5" />
          {t("settings.title")}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Scale className="size-5" />
          {t("settings.scoring.title")}
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("settings.scoring.pageDescription")}
        </p>
      </div>

      {/* Auto-rollback mode */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("settings.scoring.failGateTitle")}</CardTitle>
          <CardDescription>
            {t("settings.scoring.failGateDescription")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {prefsQ.isPending ? (
            <Skeleton className="h-8 w-48" />
          ) : (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant={liveMode ? "outline" : "default"}
                onClick={() => toggleShadowMut.mutate(0)}
                disabled={toggleShadowMut.isPending}
              >
                {t("settings.scoring.shadowRecommended")}
              </Button>
              <Button
                size="sm"
                variant={liveMode ? "default" : "outline"}
                onClick={() => toggleShadowMut.mutate(1)}
                disabled={toggleShadowMut.isPending}
              >
                {t("settings.scoring.live")}
              </Button>
              <span className="ml-2 text-xs text-muted-foreground">
                {t("settings.scoring.currently")}{" "}
                <span className="font-mono">
                  {liveMode
                    ? t("settings.scoring.liveEnforcing")
                    : t("settings.scoring.shadowLogging")}
                </span>
              </span>
            </div>
          )}
          {liveMode && (
            <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200">
              <AlertTriangle className="size-3.5 shrink-0 mt-0.5" />
              <span>
                {t("settings.scoring.liveWarning")}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Strictness tiers explained */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("settings.scoring.strictnessTitle")}</CardTitle>
          <CardDescription>
            {t("settings.scoring.strictnessDescription")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-3">
            {TIER_ORDER.map((tier) => (
              <div key={tier} className="rounded-md border p-3">
                <Badge variant="secondary" className="mb-2 capitalize">
                  {tier}
                </Badge>
                <p className="text-xs text-muted-foreground">
                  {t(TIER_DESC_KEYS[tier])}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Advanced — pass mark table */}
      <Card>
        <CardHeader className="cursor-pointer" onClick={() => setShowAdvanced((v) => !v)}>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <ChevronDown
                  className={cn(
                    "size-4 transition-transform",
                    !showAdvanced && "-rotate-90"
                  )}
                />
                {t("settings.scoring.advancedTitle")}
              </CardTitle>
              <CardDescription>
                {t("settings.scoring.advancedDescription")}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        {showAdvanced && (
          <CardContent>
            <div className="mb-3 flex justify-end">
              <Button
                size="sm"
                variant="outline"
                onClick={(e) => {
                  e.stopPropagation();
                  calibrateAllMut.mutate();
                }}
                disabled={calibrateAllMut.isPending}
              >
                <RefreshCw
                  className={cn(
                    "size-3.5",
                    calibrateAllMut.isPending && "animate-spin"
                  )}
                />
                {calibrateAllMut.isPending
                  ? t("settings.scoring.recomputing")
                  : t("settings.scoring.recomputeAll")}
              </Button>
            </div>
            {calibrationsQ.isPending ? (
              <Skeleton className="h-40 w-full" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-xs text-muted-foreground">
                      <th className="py-2 text-left font-medium">{t("settings.scoring.colStage")}</th>
                      <th className="py-2 text-left font-medium">{t("settings.scoring.colTier")}</th>
                      <th className="py-2 text-right font-medium">{t("settings.scoring.colPassMark")}</th>
                      <th className="py-2 text-right font-medium">
                        {t("settings.scoring.colReferencePapers")}
                      </th>
                      <th className="py-2 text-right font-medium">
                        {t("settings.scoring.colLastRecomputed")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {STAGE_ORDER.flatMap((stage) =>
                      TIER_ORDER.map((tier) => {
                        const row = byKey.get(`${stage}/${tier}`);
                        return (
                          <tr
                            key={`${stage}/${tier}`}
                            className="border-b border-dashed last:border-0"
                          >
                            <td className="py-2 font-medium capitalize">
                              {stage}
                            </td>
                            <td className="py-2 capitalize">
                              <Badge
                                variant="secondary"
                                className="text-xs"
                              >
                                {tier}
                              </Badge>
                            </td>
                            <td className="py-2 text-right font-mono tabular-nums">
                              {row ? row.threshold.toFixed(2) : "—"}
                            </td>
                            <td className="py-2 text-right tabular-nums">
                              {row?.anchor_count ?? 0}
                            </td>
                            <td className="py-2 text-right text-xs text-muted-foreground">
                              {row?.calibrated_at
                                ? new Date(
                                    row.calibrated_at.replace(" ", "T") + "Z"
                                  ).toLocaleString()
                                : t("settings.scoring.never")}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}
            {calibrateAllMut.isError && (
              <p className="mt-3 text-xs text-red-500">
                {(calibrateAllMut.error as Error).message}
              </p>
            )}
          </CardContent>
        )}
      </Card>
    </div>
  );
}
