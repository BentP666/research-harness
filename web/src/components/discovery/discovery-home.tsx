import type { ComponentType, ReactNode } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  BookOpenText,
  Boxes,
  Building2,
  ChevronDown,
  FlaskConical,
  GraduationCap,
  Layers3,
  Map,
  RadioTower,
  Route,
  Sparkles,
} from "lucide-react";
import {
  DISCOVERY_PROBLEM_MAP_RUN,
  DISCOVERY_PROBLEM_CATEGORIES,
  DISCOVERY_EVIDENCE_COVERAGE,
  DISCOVERY_PROBLEM_THEMES,
  getDiscoveryProblemClusters,
  getProblemCategoryEvidenceCount,
  getProblemCategoryMomentum,
  getProblemClusterEvidencePoolCount,
  getProblemClusterRecentEvidencePoolCount,
  getProblemClusterScore,
  getTopProblemCategories,
  getTopProblemClusters,
  type DiscoveryCategorySaturation,
  type DiscoveryEvidenceSide,
  type DiscoveryProblemCategory,
  type DiscoveryProblemCluster,
  type DiscoveryProblemEvidenceSignal,
  type DiscoveryProblemTheme,
  type DiscoverySolutionTrack,
} from "@/lib/discovery-product";

const sideLabel: Record<DiscoveryEvidenceSide, string> = {
  academia: "学术",
  bridge: "桥接",
  industry: "业界",
};

const sideClass: Record<DiscoveryEvidenceSide, string> = {
  academia: "bg-emerald-50 text-emerald-800 ring-emerald-900/10",
  bridge: "bg-amber-50 text-amber-800 ring-amber-900/10",
  industry: "bg-sky-50 text-sky-800 ring-sky-900/10",
};

const saturationLabel: Record<DiscoveryCategorySaturation, string> = {
  high: "偏红海",
  low: "空间大",
  medium: "升温中",
};

const saturationClass: Record<DiscoveryCategorySaturation, string> = {
  high: "bg-rose-50 text-rose-800 ring-rose-900/10",
  low: "bg-emerald-50 text-emerald-800 ring-emerald-900/10",
  medium: "bg-amber-50 text-amber-800 ring-amber-900/10",
};

export function DiscoveryHome() {
  const clusters = getDiscoveryProblemClusters();
  const categories = getTopProblemCategories(10);
  const topClusters = getTopProblemClusters(10);
  const evidenceCount = categories.reduce(
    (total, category) => total + getProblemCategoryEvidenceCount(category),
    0,
  );

  return (
    <main className="min-h-dvh bg-[#f7f4ec] text-stone-950">
      <section className="mx-auto max-w-[1320px] px-4 py-5 sm:px-6 lg:px-8">
        <header className="border-b border-stone-900/10 pb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-stone-900/10 bg-stone-50/80 px-3 py-1 text-xs font-medium text-stone-600 shadow-sm">
              <RadioTower className="size-3.5" />
              {DISCOVERY_PROBLEM_MAP_RUN.window} · {DISCOVERY_PROBLEM_MAP_RUN.model}
            </div>
            <div className="hidden text-xs text-stone-500 sm:block">
              先选大类，再看问题树、趋势与证据
            </div>
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_0.72fr] lg:items-end">
            <div>
              <h1 className="max-w-4xl text-4xl font-semibold leading-[0.96] tracking-[-0.055em] text-stone-950 md:text-6xl">
                前沿问题地图
              </h1>
              <div className="mt-4 flex flex-wrap gap-2 text-xs font-medium text-stone-600">
                <span className="rounded-full border border-stone-900/10 bg-stone-50/75 px-3 py-1">Top problem spaces</span>
                <span className="rounded-full border border-stone-900/10 bg-stone-50/75 px-3 py-1">12-month momentum</span>
                <span className="rounded-full border border-stone-900/10 bg-stone-50/75 px-3 py-1">Evidence-backed story hooks</span>
              </div>
            </div>

            <div className="grid grid-cols-3 overflow-hidden rounded-[1.5rem] border border-stone-900/10 bg-stone-50/75 shadow-sm">
              <Metric value={String(DISCOVERY_PROBLEM_CATEGORIES.length)} label="大类" />
              <Metric value={String(clusters.length)} label="问题簇" />
              <Metric value={String(evidenceCount)} label={`${DISCOVERY_EVIDENCE_COVERAGE.freshnessYearFrom}+ 证据`} />
            </div>
          </div>
        </header>

        <section className="border-b border-stone-900/10 py-5" aria-labelledby="category-map-title">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="font-mono text-xs uppercase tracking-[0.18em] text-stone-400">Category map</div>
              <h2 id="category-map-title" className="mt-1 text-2xl font-semibold tracking-[-0.04em] text-stone-950">
                10 大类
              </h2>
            </div>
            <p className="max-w-xl text-sm leading-6 text-stone-500">
              每个大类用近 12 个月趋势、拥挤度和证据覆盖度做入口判断；当前每类至少 100 条 2025+ 证据。
            </p>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            {categories.map((category, index) => (
              <CategoryCard key={category.id} category={category} rank={index + 1} />
            ))}
          </div>
        </section>

        <section className="grid gap-5 py-5 lg:grid-cols-[280px_1fr]">
          <aside className="lg:sticky lg:top-5 lg:self-start">
            <div className="rounded-[1.5rem] border border-stone-900/10 bg-stone-50/80 p-4 shadow-sm">
              <div className="flex items-center gap-2 text-sm font-semibold text-stone-900">
                <Map className="size-4" />
                大类筛选
              </div>
              <div className="mt-4 space-y-2">
                {categories.map((category, index) => (
                  <nav key={category.id} aria-label={`${category.title} navigation`}>
                    <a href={`#${category.primaryClusterIds[0]}`} className="block rounded-2xl px-3 py-2 transition hover:bg-stone-100">
                      <span className="block font-mono text-[11px] text-stone-400">#{String(index + 1).padStart(2, "0")}</span>
                      <span className="mt-1 block text-sm font-semibold leading-5 text-stone-900">{category.title}</span>
                      <span className="mt-1 block text-xs leading-5 text-stone-500">{category.shortTitle} · +{getProblemCategoryMomentum(category)}</span>
                    </a>
                  </nav>
                ))}
              </div>
            </div>

            <div className="mt-4 rounded-[1.5rem] border border-stone-900/10 bg-stone-950 p-4 text-stone-50 shadow-[0_18px_60px_-40px_rgba(28,25,23,0.9)]">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Sparkles className="size-4 text-amber-200" />
                Top 问题树
              </div>
              <div className="mt-3 space-y-3">
                {topClusters.map((cluster) => (
                  <a key={cluster.id} href={`#${cluster.id}`} className="block border-t border-white/10 pt-3 first:border-t-0 first:pt-0">
                    <div className="text-sm font-medium leading-5 text-stone-100">{cluster.title}</div>
                    <div className="mt-1 font-mono text-xs text-stone-400">score {getProblemClusterScore(cluster)}</div>
                  </a>
                ))}
              </div>
            </div>
          </aside>

          <section className="space-y-5">
            {DISCOVERY_PROBLEM_THEMES.map((theme, themeIndex) => (
              <ThemeSection key={theme.id} theme={theme} themeIndex={themeIndex} />
            ))}
          </section>
        </section>
      </section>
    </main>
  );
}

function CategoryCard({ category, rank }: { category: DiscoveryProblemCategory; rank: number }) {
  const evidenceCount = getProblemCategoryEvidenceCount(category);
  const momentum = getProblemCategoryMomentum(category);

  return (
    <Link
      href={`#${category.primaryClusterIds[0]}`}
      className="group flex min-h-[250px] flex-col rounded-[1.5rem] border border-stone-900/10 bg-stone-50/78 p-4 shadow-sm transition hover:-translate-y-0.5 hover:bg-white/90 active:translate-y-0"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="font-mono text-xs text-stone-400">#{String(rank).padStart(2, "0")}</div>
        <span className={`rounded-full px-2.5 py-1 text-[11px] ring-1 ${saturationClass[category.saturation]}`}>
          {saturationLabel[category.saturation]}
        </span>
      </div>
      <h3 className="mt-3 text-lg font-semibold leading-6 tracking-[-0.035em] text-stone-950">
        {category.title}
      </h3>
      <p className="mt-2 text-sm leading-6 text-stone-600">{category.focus}</p>
      <MiniTrend values={category.trend12m} />
      <div className="mt-auto grid grid-cols-3 gap-2 border-t border-stone-900/10 pt-3 text-xs">
        <MiniMetric label="momentum" value={`+${momentum}`} />
        <MiniMetric label="evidence" value={`${evidenceCount}`} />
        <MiniMetric label="score" value={String(category.priorityScore)} />
      </div>
      <p className="mt-3 text-xs leading-5 text-stone-500">{category.researchSpace}</p>
    </Link>
  );
}

function MiniTrend({ values }: { values: number[] }) {
  return (
    <div className="mt-4 flex h-12 items-end gap-1" aria-label="12-month trend">
      {values.map((value, index) => (
        <span
          key={`${value}-${index}`}
          className="flex-1 rounded-t-sm bg-stone-900/75 transition group-hover:bg-stone-950"
          style={{ height: `${Math.max(16, Math.round(value * 0.46))}px` }}
        />
      ))}
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-mono text-sm font-semibold text-stone-950">{value}</div>
      <div className="mt-0.5 text-[10px] uppercase tracking-[0.12em] text-stone-400">{label}</div>
    </div>
  );
}

function ThemeSection({ theme, themeIndex }: { theme: DiscoveryProblemTheme; themeIndex: number }) {
  return (
    <section id={theme.id} className="scroll-mt-5 rounded-[2rem] border border-stone-900/10 bg-stone-50/82 p-5 shadow-sm lg:p-6">
      <div className="grid gap-4 border-b border-stone-900/10 pb-5 lg:grid-cols-[0.52fr_1fr]">
        <div>
          <div className="font-mono text-xs text-stone-400">Theme {String(themeIndex + 1).padStart(2, "0")}</div>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-stone-950 md:text-3xl">
            {theme.title}
          </h2>
        </div>
        <div>
          <p className="text-sm leading-6 text-stone-700">{theme.thesis}</p>
          <p className="mt-2 text-sm leading-6 text-stone-500">{theme.userValue}</p>
        </div>
      </div>

      <div className="mt-4 divide-y divide-stone-900/10">
        {theme.clusters.map((cluster, clusterIndex) => (
          <ProblemClusterRow
            key={cluster.id}
            cluster={cluster}
            defaultOpen={themeIndex === 0 && clusterIndex === 0}
            ordinal={`${themeIndex + 1}.${clusterIndex + 1}`}
          />
        ))}
      </div>
    </section>
  );
}

function ProblemClusterRow({
  cluster,
  defaultOpen,
  ordinal,
}: {
  cluster: DiscoveryProblemCluster;
  defaultOpen: boolean;
  ordinal: string;
}) {
  const industryCount = cluster.evidence.filter((item) => item.side === "industry").length;
  const academicCount = cluster.evidence.filter((item) => item.side === "academia").length;
  const evidencePoolCount = getProblemClusterEvidencePoolCount(cluster);
  const recentEvidencePoolCount = getProblemClusterRecentEvidencePoolCount(cluster);
  const score = getProblemClusterScore(cluster);

  return (
    <details id={cluster.id} open={defaultOpen} className="group scroll-mt-6 py-4">
      <summary className="flex cursor-pointer list-none items-start gap-4 rounded-[1.25rem] p-2 transition hover:bg-stone-100/80">
        <div className="mt-1 font-mono text-xs text-stone-400">{ordinal}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-xl font-semibold tracking-[-0.035em] text-stone-950">{cluster.title}</h3>
            <Badge icon={Boxes} label={`证据池 ${evidencePoolCount}`} />
            <Badge icon={RadioTower} label={`2025+ ${recentEvidencePoolCount}`} />
            <Badge icon={Building2} label={`精选业界 ${industryCount}`} />
            <Badge icon={GraduationCap} label={`精选学术 ${academicCount}`} />
            <Badge icon={Route} label={`${cluster.solutionTracks.length} 条方案`} />
          </div>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-stone-600">{cluster.problemStatement}</p>
        </div>
        <div className="hidden items-center gap-3 sm:flex">
          <div className="font-mono text-xs text-stone-500">{score}</div>
          <ChevronDown className="size-4 text-stone-400 transition group-open:rotate-180" />
        </div>
      </summary>

      <div className="grid gap-4 px-2 pb-2 pt-4 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-4">
          <SectionBlock title="为什么现在重要" icon={Layers3}>
            <p>{cluster.whyNow}</p>
          </SectionBlock>
          <div className="grid gap-3 sm:grid-cols-2">
            <FocusBlock title="业界正在问" icon={Building2} body={cluster.industryFocus} />
            <FocusBlock title="学术正在问" icon={GraduationCap} body={cluster.academicFocus} />
          </div>
          <SectionBlock title="仍未解决" icon={BookOpenText}>
            <ul className="list-disc space-y-1 pl-5">
              {cluster.unresolvedGaps.map((gap) => (
                <li key={gap}>{gap}</li>
              ))}
            </ul>
          </SectionBlock>
        </div>

        <div className="space-y-4">
          <SectionBlock title="最新解决路线" icon={Route}>
            <div className="space-y-3">
              {cluster.solutionTracks.map((track) => (
                <SolutionTrackView key={track.title} track={track} />
              ))}
            </div>
          </SectionBlock>
          <SectionBlock title="科研故事开头" icon={FlaskConical}>
            {cluster.storyAngles.map((angle) => (
              <div key={angle.title} className="space-y-3">
                <p className="text-sm font-medium text-stone-800">{angle.title}</p>
                <p className="rounded-2xl bg-white/70 p-3 font-mono text-xs leading-5 text-stone-700">
                  {angle.opener}
                </p>
                <div className="flex flex-wrap gap-2">
                  {angle.suitableFor.map((item) => (
                    <span key={item} className="rounded-full bg-stone-100 px-2.5 py-1 text-xs text-stone-600">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </SectionBlock>
          <SectionBlock title="精选证据" icon={Boxes}>
            <p className="mb-3 rounded-2xl border border-stone-900/10 bg-white/70 p-3 text-xs leading-5 text-stone-500">
              下方只展示少量可读样例；完整 evidence pool 已由多路采集脚本验证，相关证据池 {evidencePoolCount} 条，其中 2025+ 证据 {recentEvidencePoolCount} 条。
            </p>
            <div className="space-y-2">
              {cluster.evidence.map((signal) => (
                <EvidenceLink key={`${cluster.id}-${signal.url}-${signal.title}`} signal={signal} />
              ))}
            </div>
          </SectionBlock>
        </div>
      </div>
    </details>
  );
}

function SectionBlock({
  children,
  icon: Icon,
  title,
}: {
  children: ReactNode;
  icon: ComponentType<{ className?: string }>;
  title: string;
}) {
  return (
    <section className="rounded-[1.25rem] border border-stone-900/10 bg-white/58 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-stone-800">
        <Icon className="size-4 text-stone-500" />
        {title}
      </div>
      <div className="mt-3 text-sm leading-6 text-stone-600">{children}</div>
    </section>
  );
}

function FocusBlock({
  body,
  icon: Icon,
  title,
}: {
  body: string;
  icon: ComponentType<{ className?: string }>;
  title: string;
}) {
  return (
    <div className="rounded-[1.25rem] bg-stone-100/70 p-4">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">
        <Icon className="size-3.5" />
        {title}
      </div>
      <p className="mt-3 text-sm leading-6 text-stone-700">{body}</p>
    </div>
  );
}

function SolutionTrackView({ track }: { track: DiscoverySolutionTrack }) {
  return (
    <div className="rounded-[1rem] bg-stone-100/70 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold text-stone-800">{track.title}</div>
        <span className="rounded-full bg-white/80 px-2.5 py-1 text-xs text-stone-500">{track.maturity}</span>
      </div>
      <p className="mt-2 text-sm leading-6 text-stone-600">{track.summary}</p>
      <p className="mt-2 text-xs leading-5 text-stone-500">限制：{track.currentLimit}</p>
    </div>
  );
}

function EvidenceLink({ signal }: { signal: DiscoveryProblemEvidenceSignal }) {
  return (
    <Link
      href={signal.url}
      target="_blank"
      rel="noreferrer"
      className="group flex gap-3 rounded-[1rem] bg-stone-100/70 p-3 transition hover:bg-stone-200/75"
    >
      <span className={`mt-0.5 rounded-full px-2 py-0.5 text-[11px] ring-1 ${sideClass[signal.side]}`}>
        {sideLabel[signal.side]}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium leading-5 text-stone-800">{signal.title}</span>
        <span className="mt-1 block text-xs text-stone-500">
          {signal.organization} · {signal.date}
        </span>
        <span className="mt-1 block text-xs leading-5 text-stone-600">{signal.takeaway}</span>
      </span>
      <ArrowUpRight className="mt-0.5 size-4 shrink-0 text-stone-400 transition group-hover:text-stone-800" />
    </Link>
  );
}

function Badge({ icon: Icon, label }: { icon: ComponentType<{ className?: string }>; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-stone-100 px-2.5 py-1 text-xs text-stone-600">
      <Icon className="size-3.5" />
      {label}
    </span>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-r border-stone-900/10 px-4 py-4 last:border-r-0">
      <div className="font-mono text-2xl font-semibold tracking-[-0.05em] text-stone-950">{value}</div>
      <div className="mt-1 text-xs text-stone-500">{label}</div>
    </div>
  );
}
