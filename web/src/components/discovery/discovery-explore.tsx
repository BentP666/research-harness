import Link from "next/link";
import {
  ArrowRight,
  Compass,
  Layers3,
  ListChecks,
  Sparkles,
  Telescope,
  Users2,
} from "lucide-react";
import {
  DISCOVERY_DOMAIN_TRACKS,
  DISCOVERY_PERSONA_PROFILES,
  DISCOVERY_TOPIC_CANDIDATES,
  getTopicCandidatesForDomain,
} from "@/lib/discovery-product";
import { buildNewTopicHrefFromTopicCandidate } from "@/lib/topic-prefill";
import { DiscoveryProductNav } from "./discovery-product-nav";
import { DiscoveryLiveOpportunities } from "./discovery-live-opportunities";

const compareRows = [
  { label: "适合谁", key: "fitFor" as const },
  { label: "资源需求", key: "resourceNeed" as const },
  { label: "起步周期", key: "horizon" as const },
];

export function DiscoveryExplore() {
  const compareCandidates = DISCOVERY_TOPIC_CANDIDATES.slice(0, 3);

  return (
    <div className="min-h-dvh bg-[#050711] text-slate-100">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_10%_0%,rgba(56,189,248,0.14),transparent_28%),radial-gradient(circle_at_88%_10%,rgba(16,185,129,0.10),transparent_28%)]" />
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#050711]/88 backdrop-blur-2xl">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-4 px-4 sm:px-6 lg:px-8">
          <Link href="/discovery" className="flex shrink-0 items-center gap-3">
            <div className="relative flex size-10 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-300 via-sky-300 to-emerald-300 text-slate-950">
              <Compass className="size-5" />
            </div>
            <div>
              <div className="text-sm font-semibold leading-none text-white">Explore 找方向</div>
              <div className="mt-1 text-[11px] text-slate-500">for topic-unknown researchers</div>
            </div>
          </Link>
          <DiscoveryProductNav />
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8">
        <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-[32px] border border-white/10 bg-slate-950/72 p-6 shadow-2xl shadow-black/20 backdrop-blur-xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs font-medium text-cyan-100">
              <Telescope className="size-3.5" />
              未知 topic 用户主入口
            </div>
            <h1 className="mt-5 text-4xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              从大领域收缩到一个真的能做的题
            </h1>
            <p className="mt-4 max-w-3xl text-base leading-8 text-slate-400">
              真实的新生需求不是“再给我一个热榜”，而是：我适合哪个方向、先做哪个切口、哪种题能在
              8–12 周起步，并且后面能进入 RH 深挖。
            </p>
            <div className="mt-6 grid gap-3 md:grid-cols-3">
              <SignalCard title="1. 先缩 domain" body="把大方向压到 2–3 条轨道，不从无限主题里乱选。" />
              <SignalCard title="2. 再比 candidate" body="比较 novelty、feasibility、resource，而不是只看热度。" />
              <SignalCard title="3. 最后领 starter pack" body="拿到第一周动作、检索词、初始论文和 RH 接力入口。" />
            </div>
          </div>

          <div className="rounded-[32px] border border-white/10 bg-slate-950/72 p-6 shadow-2xl shadow-black/20 backdrop-blur-xl">
            <div className="flex items-center gap-2 text-lg font-semibold text-white">
              <Users2 className="size-5 text-cyan-200" />
              默认支持的三类人
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {DISCOVERY_PERSONA_PROFILES.map((persona) => (
                <div key={persona.id} className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
                  <div className="text-sm font-semibold text-white">{persona.name}</div>
                  <div className="mt-2 text-sm leading-6 text-slate-400">{persona.need}</div>
                  <div className="mt-3 text-xs text-slate-500">
                    推荐轨道：{persona.bestFitDomainSlugs.map(getDomainName).join(" / ")}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mt-5 rounded-[32px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/20 backdrop-blur-xl">
          <div className="flex items-center gap-2 text-lg font-semibold text-white">
            <Layers3 className="size-5 text-cyan-200" />
            Domain Explorer
          </div>
          <div className="mt-4 grid gap-4 xl:grid-cols-4">
            {DISCOVERY_DOMAIN_TRACKS.map((domain) => (
              <div key={domain.slug} className="rounded-[28px] border border-white/10 bg-white/[0.035] p-4">
                <div className="text-xl font-semibold text-white">{domain.name}</div>
                <div className="mt-2 text-sm leading-6 text-slate-400">{domain.whyNow}</div>
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  <MetaChip label="适配" value={domain.thesisFit} />
                  <MetaChip label="候选题" value={`${domain.opportunityCount} 个`} />
                  <MetaChip label="难度" value={domain.difficulty} />
                  <MetaChip label="拥挤度" value={domain.saturation} />
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {domain.idealFor.map((item) => (
                    <div key={item} className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-slate-300">
                      {item}
                    </div>
                  ))}
                </div>
                <div className="mt-4 space-y-2">
                  {domain.starterProblems.map((problem) => (
                    <div key={problem} className="rounded-xl bg-black/20 px-3 py-2 text-xs text-slate-300">
                      {problem}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="mt-5">
          <DiscoveryLiveOpportunities />
        </div>

        <section className="mt-5 grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="rounded-[32px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/20 backdrop-blur-xl">
            <div className="flex items-center gap-2 text-lg font-semibold text-white">
              <ListChecks className="size-5 text-cyan-200" />
              Topic Finder · 首批候选题
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full divide-y divide-white/10 text-sm">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className="pb-3 pr-4 font-medium">候选题</th>
                    <th className="pb-3 pr-4 font-medium">Domain</th>
                    <th className="pb-3 pr-4 font-medium">Novelty</th>
                    <th className="pb-3 pr-4 font-medium">Feasible</th>
                    <th className="pb-3 pr-4 font-medium">资源</th>
                    <th className="pb-3 font-medium">周期</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {DISCOVERY_TOPIC_CANDIDATES.map((candidate) => (
                    <tr key={candidate.slug} className="align-top">
                      <td className="py-4 pr-4">
                        <div className="font-semibold text-white">{candidate.title}</div>
                        <div className="mt-1 max-w-md text-sm leading-6 text-slate-400">
                          {candidate.whyItFits}
                        </div>
                      </td>
                      <td className="py-4 pr-4 text-slate-300">{getDomainName(candidate.domainSlug)}</td>
                      <td className="py-4 pr-4 font-mono text-cyan-100">{candidate.novelty}</td>
                      <td className="py-4 pr-4 font-mono text-emerald-100">{candidate.feasibility}</td>
                      <td className="py-4 pr-4 text-slate-300">{candidate.resourceNeed}</td>
                      <td className="py-4 text-slate-300">{candidate.horizon}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-[32px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/20 backdrop-blur-xl">
            <div className="flex items-center gap-2 text-lg font-semibold text-white">
              <Sparkles className="size-5 text-cyan-200" />
              Topic compare · 先帮新手缩小选择
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3 xl:grid-cols-1">
              {compareCandidates.map((candidate) => (
                <div key={candidate.slug} className="rounded-[28px] border border-white/10 bg-white/[0.035] p-4">
                  <div className="text-base font-semibold text-white">{candidate.title}</div>
                  <div className="mt-2 text-sm leading-6 text-slate-400">{candidate.whyItFits}</div>
                  <div className="mt-4 grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
                    {compareRows.map((row) => (
                      <MetaChip
                        key={row.label}
                        label={row.label}
                        value={
                          row.key === "fitFor"
                            ? candidate.fitFor.join(" / ")
                            : String(candidate[row.key])
                        }
                      />
                    ))}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Link
                      href={buildNewTopicHrefFromTopicCandidate(
                        candidate,
                        getDomainName(candidate.domainSlug),
                      )}
                      className="inline-flex items-center gap-2 rounded-full bg-cyan-200 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100"
                    >
                      直接起 RH topic
                      <ArrowRight className="size-4" />
                    </Link>
                    <Link
                      href="/discovery/track"
                      className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-slate-300 transition hover:border-cyan-300/30 hover:text-white"
                    >
                      先加入追踪
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mt-5 grid gap-4 xl:grid-cols-2">
          {DISCOVERY_DOMAIN_TRACKS.slice(0, 2).map((domain) => (
            <div key={domain.slug} className="rounded-[32px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/20 backdrop-blur-xl">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-lg font-semibold text-white">{domain.name} starter pack</div>
                  <div className="mt-1 text-sm leading-6 text-slate-400">
                    不是只告诉用户“这个方向不错”，而是把第一周该做什么直接给出来。
                  </div>
                </div>
                <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs text-cyan-100">
                  {domain.idealFor[0]}
                </div>
              </div>
              <div className="mt-4 space-y-3">
                {getTopicCandidatesForDomain(domain.slug).slice(0, 2).map((candidate) => (
                  <div key={candidate.slug} className="rounded-[28px] border border-white/10 bg-white/[0.035] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-semibold text-white">{candidate.title}</div>
                        <div className="mt-1 text-sm leading-6 text-slate-400">{candidate.whyItFits}</div>
                      </div>
                      <div className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-slate-300">
                        {candidate.horizon}
                      </div>
                    </div>

                    <div className="mt-4 grid gap-3 lg:grid-cols-3">
                      <StarterList title="第一周动作" items={candidate.firstMoves} />
                      <StarterList title="起步论文" items={candidate.starterPack.papers} />
                      <StarterList title="第一批产出" items={candidate.starterPack.outputs} />
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2">
                      <Link
                        href={buildNewTopicHrefFromTopicCandidate(candidate, domain.name)}
                        className="inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-4 py-2 text-sm font-medium text-cyan-50"
                      >
                        用 starter pack 新建 topic
                        <ArrowRight className="size-4" />
                      </Link>
                      <div className="rounded-full border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-400">
                        RH skills: {candidate.starterPack.skills.join(" / ")}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>

        <section className="mt-5 rounded-[32px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/20 backdrop-blur-xl">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-lg font-semibold text-white">下一步怎么接入 RH</div>
              <div className="mt-1 text-sm leading-6 text-slate-400">
                一旦用户从候选 topic 中选定一个方向，Discovery 的职责就完成一半，接下来应该进入 RH。
              </div>
            </div>
            <Link
              href="/discovery/track"
              className="inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-4 py-2 text-sm font-medium text-cyan-50"
            >
              看追方向工作台
              <ArrowRight className="size-4" />
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}

function getDomainName(domainSlug: string) {
  return DISCOVERY_DOMAIN_TRACKS.find((domain) => domain.slug === domainSlug)?.name ?? domainSlug;
}

function SignalCard({ body, title }: { body: string; title: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
      <div className="text-sm font-semibold text-white">{title}</div>
      <div className="mt-2 text-sm leading-6 text-slate-400">{body}</div>
    </div>
  );
}

function MetaChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm text-slate-200">{value}</div>
    </div>
  );
}

function StarterList({ items, title }: { items: string[]; title: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{title}</div>
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <div key={item} className="text-sm leading-6 text-slate-300">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}
