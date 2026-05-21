 "use client";

import type { ComponentType } from "react";
import { useState } from "react";
import Link from "next/link";
import { Bell, Check, Compass, Database, Eye, Newspaper, Plus, Users2 } from "lucide-react";
import {
  DISCOVERY_DIGEST_ISSUES,
  DISCOVERY_HOT_TOPICS,
  DISCOVERY_WATCHLISTS,
} from "@/lib/discovery-product";
import { DiscoveryProductNav } from "./discovery-product-nav";

const WATCHLIST_STORAGE_KEY = "rh-discovery-watchlist-lanes";

function readStoredWatchlists(): string[] {
  if (typeof window === "undefined" || !window.localStorage) return [];
  try {
    const raw = window.localStorage.getItem(WATCHLIST_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function writeStoredWatchlists(names: string[]) {
  if (typeof window === "undefined" || !window.localStorage) return;
  window.localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(names));
}

export function DiscoveryWatchlists() {
  const [selectedWatchlists, setSelectedWatchlists] = useState<string[]>(
    readStoredWatchlists,
  );

  function toggleWatchlist(name: string) {
    setSelectedWatchlists((current) => {
      const next = current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name];
      writeStoredWatchlists(next);
      return next;
    });
  }

  return (
    <div className="min-h-dvh bg-[#050711] text-slate-100">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_20%_0%,rgba(56,189,248,0.14),transparent_24%),radial-gradient(circle_at_80%_0%,rgba(245,158,11,0.08),transparent_26%)]" />
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#050711]/88 backdrop-blur-2xl">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-4 px-4 sm:px-6 lg:px-8">
          <Link href="/discovery" className="flex shrink-0 items-center gap-3">
            <div className="relative flex size-10 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-300 via-sky-300 to-emerald-300 text-slate-950">
              <Compass className="size-5" />
            </div>
            <div>
              <div className="text-sm font-semibold leading-none text-white">Watchlists 观察列表</div>
              <div className="mt-1 text-[11px] text-slate-500">for topic-known researchers</div>
            </div>
          </Link>
          <DiscoveryProductNav />
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8">
        <section className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
          <div className="rounded-[32px] border border-white/10 bg-slate-950/72 p-6 shadow-xl shadow-black/20 backdrop-blur-xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs font-medium text-cyan-100">
              <Bell className="size-3.5" />
              长期跟踪而不是一次性搜索
            </div>
            <h1 className="mt-5 text-4xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              让研究者持续知道什么值得追，什么该放弃
            </h1>
            <p className="mt-4 text-base leading-8 text-slate-400">
              Watchlist 是 Discovery 的留存核心。真实研究者不是每天重新搜一次论文，而是维护少量重点轨道，持续吸收 paper、repo、benchmark、workshop 和社区变化。
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <MiniCard icon={Database} title="Watchlists" value={`${DISCOVERY_WATCHLISTS.length} 条`} />
            <MiniCard icon={Eye} title="Hot topics" value={`${DISCOVERY_HOT_TOPICS.length} 条`} />
            <MiniCard icon={Newspaper} title="Digest linkage" value={`${DISCOVERY_DIGEST_ISSUES.length} 期`} />
          </div>
        </section>

        <section className="mt-5 grid gap-4 xl:grid-cols-[1fr_0.9fr]">
          <div className="rounded-[32px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/20 backdrop-blur-xl">
            <div className="text-lg font-semibold text-white">默认观察轨道</div>
            <div className="mt-4 space-y-3">
              {DISCOVERY_WATCHLISTS.map((watchlist) => (
                <div key={watchlist.name} className="rounded-[28px] border border-white/10 bg-white/[0.035] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-base font-semibold text-white">{watchlist.name}</div>
                      <div className="mt-1 text-sm leading-6 text-slate-400">{watchlist.description}</div>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-2">
                      <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs text-cyan-100">
                        {watchlist.cadence}
                      </div>
                      <button
                        type="button"
                        onClick={() => toggleWatchlist(watchlist.name)}
                        className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-black/20 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-cyan-300/30 hover:bg-cyan-300/10"
                        aria-label={`${selectedWatchlists.includes(watchlist.name) ? "已关注" : "关注"} ${watchlist.name}`}
                      >
                        {selectedWatchlists.includes(watchlist.name) ? (
                          <Check className="size-3.5 text-emerald-200" />
                        ) : (
                          <Plus className="size-3.5 text-cyan-200" />
                        )}
                        {selectedWatchlists.includes(watchlist.name) ? "已关注" : "关注"}
                      </button>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {watchlist.trackedSignals.map((signal) => (
                      <div key={signal} className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-slate-300">
                        {signal}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[32px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/20 backdrop-blur-xl">
            <div className="flex items-center gap-2 text-lg font-semibold text-white">
              <Users2 className="size-5 text-cyan-200" />
              一个真实科研人的日常
            </div>
            <div className="mt-4 space-y-3">
              {[
                "先看 watchlist 有没有升温/降温。",
                "只打开少数真正值得处理的热点，而不是整页刷信息流。",
                "把值得做的项转成 dossier 或 RH topic。",
                "把不值得追的项明确归档，而不是继续占注意力。",
              ].map((item) => (
                <div key={item} className="rounded-2xl border border-white/10 bg-white/[0.035] p-4 text-sm leading-6 text-slate-300">
                  {item}
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function MiniCard({
  icon: Icon,
  title,
  value,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  value: string;
}) {
  return (
    <div className="rounded-[28px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/20 backdrop-blur-xl">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-300">
        <Icon className="size-4 text-cyan-200" />
        {title}
      </div>
      <div className="mt-4 text-3xl font-semibold text-white">{value}</div>
    </div>
  );
}
