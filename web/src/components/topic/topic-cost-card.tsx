"use client";

import { useQuery } from "@tanstack/react-query";
import { Coins, Zap, TrendingUp } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchProvenanceSummary } from "@/lib/api";
import { useT } from "@/lib/i18n-provider";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface TopicCostCardProps {
  topicId: number;
}

export function TopicCostCard({ topicId }: TopicCostCardProps) {
  const { t } = useT();
  const { data, isPending, isError } = useQuery({
    queryKey: ["provenance-summary", topicId],
    queryFn: () => fetchProvenanceSummary(topicId),
    refetchInterval: 5000, // short polling, per v2 plan
  });

  if (isPending) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">{t("costCard.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">{t("costCard.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-xs text-muted-foreground">
            {t("costCard.noActivity")}
          </div>
        </CardContent>
      </Card>
    );
  }

  const totalPrompt = data.total_prompt_tokens ?? 0;
  const totalCompletion = data.total_completion_tokens ?? 0;
  const totalTokens = totalPrompt + totalCompletion;
  const callCount = data.total_records ?? 0;

  // Primitive-level token breakdown for chart
  const chartData = (data.by_primitive ?? [])
    .slice(0, 10)
    .map((row) => ({
      name:
        row.primitive.length > 18
          ? row.primitive.slice(0, 15) + "…"
          : row.primitive,
      fullName: row.primitive,
      tokens: row.prompt_tokens + row.completion_tokens,
      calls: row.call_count,
    }))
    .filter((row) => row.tokens > 0)
    .sort((a, b) => b.tokens - a.tokens);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">{t("costCard.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Top-line stats — tokens only, no $ */}
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-md border bg-muted/20 p-2">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Coins className="size-3" />
              {t("costCard.tokens")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {formatNumber(totalTokens)}
            </div>
          </div>
          <div className="rounded-md border bg-muted/20 p-2">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Zap className="size-3" />
              prompt / completion
            </div>
            <div className="mt-1 text-sm font-semibold tabular-nums">
              {formatNumber(totalPrompt)} / {formatNumber(totalCompletion)}
            </div>
          </div>
          <div className="rounded-md border bg-muted/20 p-2">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <TrendingUp className="size-3" />
              {t("costCard.calls")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">{callCount}</div>
          </div>
        </div>

        {/* Token breakdown by primitive */}
        {chartData.length > 0 ? (
          <div>
            <div className="mb-1 text-xs font-medium text-muted-foreground">
              {t("costCard.spendByPrimitive")}
            </div>
            <div className="h-40 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 10 }}
                    angle={-30}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const p = payload[0].payload as {
                        fullName: string;
                        tokens: number;
                        calls: number;
                      };
                      return (
                        <div className="rounded-md border bg-background p-2 text-xs shadow">
                          <div className="font-medium">{p.fullName}</div>
                          <div>{formatNumber(p.tokens)} tokens</div>
                          <div>{p.calls} {t("costCard.calls")}</div>
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="tokens" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        ) : (
          <div className="rounded-md border border-dashed p-3 text-center text-xs text-muted-foreground">
            {t("costCard.noActivity")}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}
