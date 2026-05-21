import Link from "next/link";
import { ArrowUpRight, Clock3, ShieldAlert, Sparkles } from "lucide-react";
import type { DiscoveryOpportunity } from "@/lib/discovery-product";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const horizonLabel: Record<DiscoveryOpportunity["horizon"], string> = {
  "act-now": "Act now",
  watch: "Watch",
  frontier: "Frontier",
};

const categoryRing: Record<DiscoveryOpportunity["category"], string> = {
  "Agent Evaluation": "from-cyan-400 to-blue-500",
  "Agent Security": "from-rose-400 to-orange-500",
  AI4Code: "from-violet-400 to-fuchsia-500",
  "AI Infrastructure": "from-emerald-400 to-teal-500",
  Multimodal: "from-amber-300 to-pink-500",
};

export function OpportunityCard({ opportunity, rank }: { opportunity: DiscoveryOpportunity; rank: number }) {
  return (
    <article className="group relative overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-2xl hover:shadow-slate-200/80 dark:border-white/10 dark:bg-slate-900/70 dark:hover:shadow-slate-950/40">
      <div className={cn("absolute inset-x-0 top-0 h-1 bg-gradient-to-r", categoryRing[opportunity.category])} />
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-slate-950 font-mono text-sm font-semibold text-white dark:bg-white dark:text-slate-950">
            {String(rank).padStart(2, "0")}
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{opportunity.category}</Badge>
              <Badge variant={opportunity.horizon === "act-now" ? "default" : "outline"}>{horizonLabel[opportunity.horizon]}</Badge>
            </div>
            <h3 className="mt-3 text-xl font-semibold tracking-tight text-slate-950 dark:text-white">
              {opportunity.title}
            </h3>
          </div>
        </div>
        <Link
          href={`/discovery/opportunities/${opportunity.slug}`}
          className="flex size-9 shrink-0 items-center justify-center rounded-full border border-slate-200 text-slate-500 transition group-hover:border-slate-950 group-hover:bg-slate-950 group-hover:text-white dark:border-white/10 dark:group-hover:bg-white dark:group-hover:text-slate-950"
          aria-label={`打开 ${opportunity.title}`}
        >
          <ArrowUpRight className="size-4" />
        </Link>
      </div>

      <p className="mt-4 text-sm leading-6 text-slate-600 dark:text-slate-300">{opportunity.oneLiner}</p>

      {opportunity.brief.goal_previews.length > 0 && (
        <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-300/20 dark:bg-emerald-300/10">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700 dark:text-emerald-200">
              Goal-ready
            </span>
            <span className="font-mono text-xs text-emerald-700 dark:text-emerald-200">
              {Math.round(opportunity.brief.readiness.goalability * 100)}%
            </span>
          </div>
          <p className="mt-2 line-clamp-2 text-sm leading-5 text-emerald-950 dark:text-emerald-50/80">
            {opportunity.brief.goal_previews[0].title}
          </p>
        </div>
      )}

      <div className="mt-5 grid grid-cols-4 gap-2">
        <Score label="Impact" value={opportunity.radar.impact} />
        <Score label="Momentum" value={opportunity.radar.momentum} />
        <Score label="Feasible" value={opportunity.radar.feasibility} />
        <Score label="Sat." value={opportunity.radar.saturation} inverse />
      </div>

      <div className="mt-5 space-y-3 rounded-2xl bg-slate-50 p-4 dark:bg-slate-950/60">
        <div className="flex gap-2 text-sm">
          <Sparkles className="mt-0.5 size-4 shrink-0 text-amber-500" />
          <p className="leading-5 text-slate-700 dark:text-slate-300">{opportunity.productThesis}</p>
        </div>
        <div className="flex gap-2 text-sm">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-rose-500" />
          <p className="leading-5 text-slate-600 dark:text-slate-400">{opportunity.counterPosition}</p>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {opportunity.audience.map((audience) => (
          <span key={audience} className="rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-600 dark:border-white/10 dark:text-slate-300">
            {audience}
          </span>
        ))}
      </div>

      <div className="mt-5 border-t border-slate-100 pt-4 dark:border-white/10">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
          <Clock3 className="size-3.5" />
          why now
        </div>
        <p className="line-clamp-3 text-sm leading-6 text-slate-600 dark:text-slate-300">{opportunity.brief.why_now}</p>
      </div>
    </article>
  );
}

function Score({ label, value, inverse = false }: { label: string; value: number; inverse?: boolean }) {
  const tone = inverse ? 100 - value : value;
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-2.5 dark:border-white/10 dark:bg-slate-900">
      <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400">{label}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums text-slate-950 dark:text-white">{value}</div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div className="h-full rounded-full bg-slate-950 dark:bg-white" style={{ width: `${tone}%` }} />
      </div>
    </div>
  );
}
