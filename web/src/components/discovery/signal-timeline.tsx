import { ExternalLink } from "lucide-react";
import type { DiscoverySignalSource } from "@/lib/discovery-product";

export function SignalTimeline({ signals }: { signals: DiscoverySignalSource[] }) {
  return (
    <div className="space-y-3">
      {signals.map((signal, index) => (
        <a
          key={`${signal.title}-${signal.date}`}
          href={signal.url}
          target="_blank"
          rel="noreferrer"
          className="group grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-slate-950 hover:shadow-lg dark:border-white/10 dark:bg-slate-900/70 dark:hover:border-white/40 md:grid-cols-[120px_1fr]"
        >
          <div className="flex items-center gap-3 md:block">
            <div className="flex size-8 items-center justify-center rounded-full bg-slate-950 font-mono text-xs font-semibold text-white dark:bg-white dark:text-slate-950">
              {index + 1}
            </div>
            <div className="md:mt-3">
              <div className="font-mono text-xs text-slate-500">{signal.date}</div>
              <div className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">{signal.kind}</div>
            </div>
          </div>
          <div>
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-semibold text-slate-950 dark:text-white">{signal.title}</h3>
              <ExternalLink className="size-4 shrink-0 text-slate-400 transition group-hover:text-slate-950 dark:group-hover:text-white" />
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{signal.takeaway}</p>
          </div>
        </a>
      ))}
    </div>
  );
}
