import Link from "next/link";
import { Compass, ExternalLink, Newspaper, Sparkles } from "lucide-react";
import { DISCOVERY_DIGEST_ISSUES } from "@/lib/discovery-product";
import { DiscoveryProductNav } from "./discovery-product-nav";

export function DiscoveryDigest() {
  return (
    <div className="min-h-dvh bg-[#050711] text-slate-100">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_12%_0%,rgba(56,189,248,0.14),transparent_26%),radial-gradient(circle_at_88%_0%,rgba(168,85,247,0.10),transparent_24%)]" />
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#050711]/88 backdrop-blur-2xl">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-4 px-4 sm:px-6 lg:px-8">
          <Link href="/discovery" className="flex shrink-0 items-center gap-3">
            <div className="relative flex size-10 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-300 via-sky-300 to-emerald-300 text-slate-950">
              <Compass className="size-5" />
            </div>
            <div>
              <div className="text-sm font-semibold leading-none text-white">Digest 周报归档</div>
              <div className="mt-1 text-[11px] text-slate-500">editorial surface for discovery</div>
            </div>
          </Link>
          <DiscoveryProductNav />
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8">
        <section className="rounded-[32px] border border-white/10 bg-slate-950/72 p-6 shadow-xl shadow-black/20 backdrop-blur-xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs font-medium text-cyan-100">
            <Sparkles className="size-3.5" />
            从产品信号到可发布内容
          </div>
          <h1 className="mt-5 text-4xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
            Discovery 不是只给内部看，它还应该持续对外发布研究机会周报
          </h1>
          <p className="mt-4 max-w-4xl text-base leading-8 text-slate-400">
            周报归档是产品可信度的一部分。它把内部的 signal triage 结果变成对外可读的 issue，也让用户知道这个系统不是一次性演示，而是在持续维护。
          </p>
        </section>

        <section className="mt-5 grid gap-4 xl:grid-cols-2">
          {DISCOVERY_DIGEST_ISSUES.map((issue) => (
            <article key={issue.id} className="rounded-[32px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/20 backdrop-blur-xl">
              <div className="flex items-center justify-between gap-3">
                <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
                  <Newspaper className="size-3.5 text-cyan-200" />
                  {issue.date}
                </div>
                <div className="text-xs text-slate-500">{issue.focus}</div>
              </div>
              <h2 className="mt-5 text-2xl font-semibold tracking-tight text-white">{issue.title}</h2>
              <p className="mt-3 text-sm leading-7 text-slate-400">{issue.topLine}</p>
              <div className="mt-4 space-y-2">
                {issue.highlights.map((highlight) => (
                  <div key={highlight} className="rounded-2xl border border-white/10 bg-white/[0.035] px-4 py-3 text-sm text-slate-300">
                    {highlight}
                  </div>
                ))}
              </div>
              <Link
                href={issue.href}
                className="mt-5 inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-4 py-2 text-sm font-medium text-cyan-50"
              >
                打开 issue
                <ExternalLink className="size-4" />
              </Link>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
