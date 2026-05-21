import Link from "next/link";
import { ArrowUpRight, Crosshair } from "lucide-react";
import type { DiscoveryOpportunity } from "@/lib/discovery-product";
import { cn } from "@/lib/utils";

const categoryTone: Record<DiscoveryOpportunity["category"], string> = {
  "Agent Evaluation": "bg-cyan-300 shadow-cyan-400/40",
  "Agent Security": "bg-rose-300 shadow-rose-400/40",
  AI4Code: "bg-violet-300 shadow-violet-400/40",
  "AI Infrastructure": "bg-emerald-300 shadow-emerald-400/40",
  Multimodal: "bg-amber-300 shadow-amber-400/40",
};

function axisPosition(value: number): string {
  return `${Math.max(7, Math.min(93, value))}%`;
}

export function RadarMap({ opportunities }: { opportunities: DiscoveryOpportunity[] }) {
  return (
    <section className="rounded-[2rem] border border-white/10 bg-slate-950 p-5 text-white shadow-2xl shadow-slate-950/30 lg:p-7">
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-cyan-100">
            <Crosshair className="size-3.5" />
            Opportunity Radar · CS / AI
          </div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight md:text-3xl">
            先找“高影响、未拥挤、能开工”的方向
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
            横轴是方向拥挤度，纵轴是潜在影响力；点越亮代表近期动量越强，外圈越大代表 30 天内落地可行性越高。
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs text-slate-300 sm:grid-cols-3">
          {opportunities.map((item) => (
            <div key={item.slug} className="flex items-center gap-2">
              <span className={cn("size-2.5 rounded-full", categoryTone[item.category])} />
              <span>{item.category}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="relative h-[420px] overflow-hidden rounded-[1.5rem] border border-white/10 bg-[radial-gradient(circle_at_20%_20%,rgba(34,211,238,0.16),transparent_28%),radial-gradient(circle_at_80%_25%,rgba(168,85,247,0.16),transparent_30%),linear-gradient(135deg,rgba(15,23,42,0.96),rgba(2,6,23,0.98))] p-4">
        <div className="absolute inset-10 rounded-2xl border border-white/10" />
        <div className="absolute left-10 right-10 top-1/2 border-t border-dashed border-white/15" />
        <div className="absolute bottom-10 top-10 left-1/2 border-l border-dashed border-white/15" />
        <div className="absolute left-4 top-4 text-[11px] uppercase tracking-[0.22em] text-slate-500">High impact</div>
        <div className="absolute bottom-4 right-4 text-[11px] uppercase tracking-[0.22em] text-slate-500">Crowded</div>
        <div className="absolute bottom-4 left-4 text-[11px] uppercase tracking-[0.22em] text-slate-500">Underserved</div>

        {opportunities.map((item, index) => {
          const size = 18 + item.radar.feasibility / 4;
          return (
            <Link
              key={item.slug}
              href={`/discovery/opportunities/${item.slug}`}
              className="group absolute -translate-x-1/2 -translate-y-1/2 focus:outline-none"
              style={{
                left: axisPosition(item.radar.saturation),
                top: axisPosition(100 - item.radar.impact),
              }}
              aria-label={`Open ${item.title}`}
            >
              <span
                className={cn(
                  "absolute rounded-full opacity-25 blur-md transition group-hover:opacity-50",
                  categoryTone[item.category],
                )}
                style={{ width: size * 2.7, height: size * 2.7, left: -size * 0.85, top: -size * 0.85 }}
              />
              <span
                className={cn(
                  "relative flex items-center justify-center rounded-full border border-white/70 text-[11px] font-bold text-slate-950 shadow-xl ring-4 ring-white/10 transition group-hover:scale-110 group-focus:scale-110",
                  categoryTone[item.category],
                )}
                style={{ width: size, height: size }}
              >
                {index + 1}
              </span>
              <span className="pointer-events-none absolute left-1/2 top-full mt-3 hidden w-52 -translate-x-1/2 rounded-2xl border border-white/10 bg-slate-900/95 p-3 text-left shadow-xl backdrop-blur md:group-hover:block">
                <span className="block text-xs font-semibold text-white">{item.title}</span>
                <span className="mt-1 block text-[11px] leading-4 text-slate-300">动量 {item.radar.momentum} · 可行 {item.radar.feasibility}</span>
              </span>
            </Link>
          );
        })}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <RadarMetric label="最佳立即开工" value="Agent 安全 / Agent 评测" />
        <RadarMetric label="最适合系统论文" value="Agentic inference 可观测性" />
        <RadarMetric label="最高动量" value="Coding agent → 算法 / kernel" />
      </div>
    </section>
  );
}

function RadarMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className="mt-2 flex items-center justify-between gap-3 text-sm font-semibold text-slate-100">
        <span>{value}</span>
        <ArrowUpRight className="size-4 text-cyan-200" />
      </div>
    </div>
  );
}
