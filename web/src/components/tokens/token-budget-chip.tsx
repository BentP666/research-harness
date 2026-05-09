"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Coins } from "lucide-react";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { fetchProvenanceSummary, fetchLedger } from "@/lib/api";
import { useT } from "@/lib/i18n-provider";
import { cn } from "@/lib/utils";

/**
 * Header-persistent token usage chip. We intentionally avoid $ estimates
 * because per-provider rate cards vary and can mislead. Tokens are honest.
 * Tap for a breakdown by model + stage.
 */
export function TokenBudgetChip() {
  const { t } = useT();

  const summaryQ = useQuery({
    queryKey: ["provenance-summary-global"],
    queryFn: () => fetchProvenanceSummary(),
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

  const sinceMonth = new Date().toISOString().slice(0, 7) + "-01";
  const byAgentQ = useQuery({
    queryKey: ["ledger-by-agent", sinceMonth],
    queryFn: () => fetchLedger({ since: sinceMonth, group_by: "agent" }),
    staleTime: 60_000,
  });
  const byStageQ = useQuery({
    queryKey: ["ledger-by-stage", sinceMonth],
    queryFn: () => fetchLedger({ since: sinceMonth, group_by: "stage" }),
    staleTime: 60_000,
  });

  const prompt = summaryQ.data?.total_prompt_tokens ?? 0;
  const completion = summaryQ.data?.total_completion_tokens ?? 0;
  const total = prompt + completion;

  return (
    <Popover>
      <PopoverTrigger
        render={
          <button
            type="button"
            className={cn(
              "group inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-all",
              "bg-slate-50 text-slate-700 border-slate-200 hover:border-foreground/30",
              "dark:bg-slate-900 dark:text-slate-300 dark:border-slate-700"
            )}
          >
            <Coins className="size-3" />
            <span className="tabular-nums">
              {formatTokens(total)}
              <span className="ml-1 text-muted-foreground">tok</span>
            </span>
          </button>
        }
      />
      <PopoverContent align="end" className="w-80 p-3">
        <div className="space-y-3">
          <div>
            <p className="text-sm font-semibold">{t("tokens.thisMonth")}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {t("tokens.promptCompletionSplit", {
                prompt: formatTokens(prompt),
                completion: formatTokens(completion),
              })}
            </p>
          </div>

          {/* By-model breakdown */}
          {byAgentQ.data && byAgentQ.data.length > 0 && (
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                {t("tokens.byModel")}
              </p>
              <div className="space-y-1">
                {(byAgentQ.data as Array<Record<string, unknown>>)
                  .slice(0, 4)
                  .map((row, i) => {
                    const name = (row.nickname as string) ?? (row.model as string) ?? "unknown";
                    const totalTok =
                      (Number(row.total_prompt) || 0) +
                      (Number(row.total_completion) || 0);
                    return (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="truncate font-medium">{name}</span>
                        <span className="ml-2 shrink-0 tabular-nums text-muted-foreground">
                          {formatTokens(totalTok)}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* By-stage breakdown */}
          {byStageQ.data && byStageQ.data.length > 0 && (
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                {t("tokens.byStage")}
              </p>
              <div className="space-y-1">
                {(byStageQ.data as Array<Record<string, unknown>>)
                  .slice(0, 6)
                  .map((row, i) => {
                    const stage = (row.stage as string) ?? "—";
                    const totalTok =
                      (Number(row.total_prompt) || 0) +
                      (Number(row.total_completion) || 0);
                    return (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="truncate font-medium capitalize">{stage}</span>
                        <span className="ml-2 shrink-0 tabular-nums text-muted-foreground">
                          {formatTokens(totalTok)}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs flex-1"
              render={<Link href="/budgets" />}
            >
              {t("tokens.fullBreakdown")}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(Math.round(n));
}
