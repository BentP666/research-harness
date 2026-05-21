"use client";

import Link from "next/link";
import { ArrowUpRight, FileJson2, Newspaper, Radar, SearchCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { DiscoverOpportunityBrief, DiscoverWeeklyReport } from "@/lib/api";
import { buildNewTopicHrefFromDiscoverBrief } from "@/lib/topic-prefill";

export function DiscoverWeeklyShowcase({
  report,
  loading = false,
}: {
  report: DiscoverWeeklyReport | null | undefined;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <Card className="border-dashed">
        <CardContent className="p-6 text-sm text-muted-foreground">
          Loading RH Discover Weekly…
        </CardContent>
      </Card>
    );
  }

  if (!report) {
    return (
      <Card className="border-dashed">
        <CardContent className="space-y-2 p-6">
          <h2 className="font-serif text-xl font-medium">
            No RH Discover Weekly report yet
          </h2>
          <p className="text-sm text-muted-foreground">
            Generate one with <code>rh discover weekly --sample</code> or connect
            the Discover API.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <section className="space-y-4" aria-labelledby="discover-weekly-title">
      <Card className="overflow-hidden border-indigo-200/70 bg-gradient-to-br from-indigo-50 via-white to-orange-50 dark:border-indigo-900/40 dark:from-indigo-950/30 dark:via-slate-950 dark:to-orange-950/20">
        <CardContent className="grid gap-6 p-6 md:grid-cols-[1.3fr_0.7fr]">
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-xs font-medium text-indigo-700 dark:text-indigo-300">
              <Newspaper className="size-4" />
              {report.product} · {report.generated_at}
            </div>
            <div>
              <h2
                id="discover-weekly-title"
                className="font-serif text-3xl font-medium tracking-tight"
              >
                {report.title}
              </h2>
              <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                {report.subtitle}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge className="bg-indigo-600 text-white">
                {report.brief_count} OpportunityBriefs
              </Badge>
              <Badge variant="outline" className="font-mono">
                {report.cadence}
              </Badge>
              <Badge variant="outline" className="font-mono">
                {report.status}
              </Badge>
              <Badge variant="outline" className="font-mono">
                {report.issue_id}
              </Badge>
              <Badge variant="outline" className="gap-1">
                <FileJson2 className="size-3" />
                JSON handoff ready
              </Badge>
              <Badge variant="outline" className="gap-1">
                <SearchCheck className="size-3" />
                RH Core queries included
              </Badge>
            </div>
          </div>
          <div className="rounded-2xl border bg-background/80 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Radar className="size-4 text-indigo-600" />
              Showcase contract
            </div>
            <ol className="mt-3 space-y-2 text-xs text-muted-foreground">
              <li>1. What happened?</li>
              <li>2. Why does it matter now?</li>
              <li>3. What direction could it become?</li>
              <li>4. What evidence and risks support it?</li>
              <li>5. How can it be handed off to RH?</li>
            </ol>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        {report.briefs.map((brief, index) => (
          <OpportunityBriefCard
            key={brief.rh_handoff.topic_name}
            brief={brief}
            rank={index + 1}
          />
        ))}
      </div>
    </section>
  );
}

function OpportunityBriefCard({
  brief,
  rank,
}: {
  brief: DiscoverOpportunityBrief;
  rank: number;
}) {
  const fitAverage =
    (brief.fit_score.trend +
      brief.fit_score.novelty +
      brief.fit_score.feasibility +
      brief.fit_score.user_fit +
      (1 - brief.fit_score.risk)) /
    5;

  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <CardHeader className="space-y-3 pb-3">
        <div className="flex items-center justify-between gap-2">
          <Badge variant="outline" className="font-mono text-[10px]">
            #{rank}
          </Badge>
          <Badge
            className={cn(
              "font-mono text-[10px]",
              fitAverage >= 0.7
                ? "bg-emerald-600 text-white"
                : "bg-amber-500 text-white"
            )}
          >
            fit {(fitAverage * 100).toFixed(0)}%
          </Badge>
        </div>
        <CardTitle className="text-base leading-tight">{brief.title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <div className="space-y-2">
          <p className="text-xs leading-relaxed text-muted-foreground">
            {brief.summary}
          </p>
          <p className="text-xs leading-relaxed">
            <span className="font-semibold">Why now: </span>
            {brief.why_now}
          </p>
        </div>

        <div className="space-y-2">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Signals
          </div>
          <div className="space-y-2">
            {brief.signals.slice(0, 2).map((signal) => (
              <a
                key={`${signal.type}-${signal.title}`}
                href={signal.url}
                target="_blank"
                rel="noreferrer"
                className="block rounded-lg border p-2 text-xs transition-colors hover:bg-muted/50"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{signal.title}</span>
                  <Badge variant="secondary" className="text-[10px]">
                    {signal.type}
                  </Badge>
                </div>
                <p className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">
                  {signal.reason}
                </p>
              </a>
            ))}
          </div>
        </div>

        <div className="mt-auto space-y-2 rounded-xl border bg-muted/30 p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            RH handoff
          </div>
          <div className="text-xs font-medium">{brief.rh_handoff.topic_name}</div>
          <div className="flex flex-wrap gap-1">
            {brief.rh_handoff.initial_queries.slice(0, 2).map((query) => (
              <Badge
                key={query}
                variant="outline"
                className="max-w-full truncate text-[10px]"
                title={query}
              >
                {query}
              </Badge>
            ))}
          </div>
          <div className="flex flex-wrap gap-1">
            {brief.rh_handoff.suggested_primitives.map((primitive) => (
              <Badge key={primitive} variant="secondary" className="text-[10px]">
                {primitive}
              </Badge>
            ))}
          </div>
        </div>

        <Button
          render={<Link href={buildNewTopicHrefFromDiscoverBrief(brief)} />}
          variant="outline"
          size="sm"
          className="justify-between"
        >
          Turn into RH topic
          <ArrowUpRight className="size-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}
