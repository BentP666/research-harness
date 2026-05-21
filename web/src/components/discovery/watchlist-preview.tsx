import { Bell, RadioTower } from "lucide-react";
import { DISCOVERY_WATCHLISTS } from "@/lib/discovery-product";

export function WatchlistPreview() {
  return (
    <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-slate-900/70">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 dark:bg-white/10 dark:text-slate-300">
            <RadioTower className="size-3.5" />
            Watchlists
          </div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight">不是一次搜索，是持续雷达</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-300">
            Discovery 后续应像产品一样维护 watchlist：自动吸收 paper / repo / product / workshop 信号，定期输出“值得开工”的机会变化。
          </p>
        </div>
        <Bell className="hidden size-8 text-slate-400 md:block" />
      </div>
      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {DISCOVERY_WATCHLISTS.map((watchlist) => (
          <div key={watchlist.name} className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-white/10 dark:bg-slate-950/50">
            <div className="text-sm font-semibold text-slate-950 dark:text-white">{watchlist.name}</div>
            <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{watchlist.description}</p>
            <div className="mt-3 font-mono text-xs text-slate-500">{watchlist.cadence}</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {watchlist.trackedSignals.map((signal) => (
                <span key={signal} className="rounded-full bg-white px-2 py-1 text-[11px] text-slate-500 ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-white/10">
                  {signal}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
