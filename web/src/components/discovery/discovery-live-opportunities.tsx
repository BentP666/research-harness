"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowUpRight, Loader2, RadioTower } from "lucide-react";
import {
  fetchDiscoverOpportunities,
  type DiscoverOpportunityCard,
} from "@/lib/api";

export function DiscoveryLiveOpportunities() {
  const [opportunities, setOpportunities] = useState<DiscoverOpportunityCard[]>([]);
  const [issueId, setIssueId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadOpportunities() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetchDiscoverOpportunities({ sample: false });
        if (!isMounted) return;
        setOpportunities(response.opportunities);
        setIssueId(response.issue_id);
      } catch (err) {
        if (!isMounted) return;
        setError(
          err instanceof Error ? err.message : "Failed to load live opportunities",
        );
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    void loadOpportunities();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <section className="rounded-[32px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/20 backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-lg font-semibold text-white">
            <RadioTower className="size-5 text-cyan-200" />
            Live Opportunity Feed
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            从 `/api/discover/opportunities` 读取已发布 issue，而不是只展示静态样例。
          </p>
        </div>
        {issueId ? (
          <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 font-mono text-xs text-cyan-100">
            {issueId}
          </div>
        ) : null}
      </div>

      {isLoading ? (
        <div className="mt-4 flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-400">
          <Loader2 className="size-4 animate-spin" />
          正在读取 /api/discover/opportunities
        </div>
      ) : null}

      {error ? (
        <div className="mt-4 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm leading-6 text-rose-100">
          {error}
        </div>
      ) : null}

      {!isLoading && !error ? (
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {opportunities.map((opportunity) => (
            <Link
              key={opportunity.slug}
              href={`/discovery/opportunities/${opportunity.slug}`}
              className="group rounded-[24px] border border-white/10 bg-white/[0.035] p-4 transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.04]"
              aria-label={`打开 ${opportunity.title}`}
            >
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-semibold leading-6 text-white">
                  {opportunity.title}
                </h3>
                <ArrowUpRight className="size-4 shrink-0 text-slate-600 transition group-hover:text-cyan-100" />
              </div>
              <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-400">
                {opportunity.summary}
              </p>
              <div className="mt-4 rounded-2xl border border-emerald-300/20 bg-emerald-300/10 p-3">
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="font-semibold uppercase tracking-[0.16em] text-emerald-100">
                    goalability
                  </span>
                  <span className="font-mono text-emerald-100">
                    {Math.round(opportunity.readiness.goalability * 100)}%
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-sm leading-5 text-emerald-50/80">
                  {opportunity.goal_previews[0]?.title ?? "Not goal-ready yet"}
                </p>
              </div>
            </Link>
          ))}
        </div>
      ) : null}
    </section>
  );
}
