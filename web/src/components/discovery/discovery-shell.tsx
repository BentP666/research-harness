"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Bell,
  Boxes,
  ChevronRight,
  CheckCircle2,
  CircleDot,
  Compass,
  Database,
  Eye,
  Filter,
  Flame,
  Layers3,
  Newspaper,
  Radar,
  RadioTower,
  Route,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";
import {
  DISCOVERY_HOT_TOPICS,
  DISCOVERY_LAST_UPDATED,
  DISCOVERY_OCEAN_META,
  DISCOVERY_OPPORTUNITIES,
  DISCOVERY_SOURCE_STATUS,
  DISCOVERY_WATCHLISTS,
  type DiscoveryHotTopic,
  type DiscoveryWindow,
  getDiscoverySnapshot,
  getHotTopics,
  getOpportunity,
  getTotalSignalCount,
} from "@/lib/discovery-product";
import { buildNewTopicHrefFromDiscoverBrief } from "@/lib/topic-prefill";
import { cn } from "@/lib/utils";
import { DiscoveryProductNav } from "./discovery-product-nav";

const OBSERVED_TOPICS_STORAGE_KEY = "rh-discovery-observed-topics";

function normalizeSearchText(value: string): string {
  return value.trim().toLowerCase();
}

function matchesTopic(topic: DiscoveryHotTopic, query: string): boolean {
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) return true;

  const searchableFields = [
    topic.title,
    topic.shortTitle,
    topic.category,
    topic.summary,
    topic.whyHot,
    topic.researchQuestion,
    topic.oceanLabel,
    topic.recommendedAction,
    ...topic.tags,
  ];

  return searchableFields.some((field) => normalizeSearchText(field).includes(normalizedQuery));
}

function getMatchedTags(topic: DiscoveryHotTopic, query: string): string[] {
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) return [];
  return topic.tags.filter((tag) => normalizeSearchText(tag).includes(normalizedQuery));
}

function getBrowserStorage(): Storage | null {
  if (typeof window === "undefined" || !("localStorage" in window)) return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function readObservedTopicIdsFromStorage(): string[] {
  try {
    const storage = getBrowserStorage();
    const raw = storage?.getItem(OBSERVED_TOPICS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((id): id is string =>
      typeof id === "string" && DISCOVERY_HOT_TOPICS.some((topic) => topic.id === id),
    );
  } catch {
    return [];
  }
}

const windowTabs: Array<{ id: DiscoveryWindow; label: string; hint: string }> = [
  { id: "today", label: "今日热点", hint: "过去 24 小时新增/升温" },
  { id: "week", label: "本周升温", hint: "7 日趋势与跨源共振" },
  { id: "month", label: "本月趋势", hint: "30 日研究机会判断" },
];

const navItems = [
  { label: "热点发现", icon: Flame, active: true },
  { label: "趋势雷达", icon: Radar, active: false },
  { label: "机会池", icon: Target, active: false },
  { label: "我的观察", icon: Eye, active: false },
  { label: "来源管理", icon: Database, active: false },
];

type SourceFilter = "all" | keyof DiscoveryHotTopic["sourceCounts"];

const sourceLabels: Array<{ key: keyof DiscoveryHotTopic["sourceCounts"]; label: string }> = [
  { key: "paper", label: "论文" },
  { key: "repo", label: "开源" },
  { key: "product", label: "产品" },
  { key: "benchmark", label: "评测" },
  { key: "workshop", label: "会议" },
  { key: "community", label: "社区" },
];

const sourceFilters: Array<{ key: SourceFilter; label: string; hint: string }> = [
  { key: "all", label: "全来源", hint: "综合排序" },
  { key: "paper", label: "论文", hint: "arXiv / OpenReview" },
  { key: "repo", label: "开源", hint: "GitHub / HF" },
  { key: "product", label: "产品", hint: "模型与平台发布" },
  { key: "benchmark", label: "评测", hint: "榜单与任务集" },
  { key: "community", label: "社区", hint: "讨论热度" },
];

export function DiscoveryShell() {
  const [window, setWindow] = useState<DiscoveryWindow>("today");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [query, setQuery] = useState("");
  const windowTopics = useMemo(() => getHotTopics(window), [window]);
  const topics = useMemo(() => {
    const scoped =
      sourceFilter === "all"
        ? windowTopics
        : windowTopics.filter((topic) => topic.sourceCounts[sourceFilter] > 0);

    return [...scoped]
      .filter((topic) => matchesTopic(topic, query))
      .sort((a, b) => {
      if (sourceFilter === "all") return b.heatScore - a.heatScore;
      return (
        b.sourceCounts[sourceFilter] - a.sourceCounts[sourceFilter] ||
        b.heatScore - a.heatScore
      );
      });
  }, [query, sourceFilter, windowTopics]);
  const snapshot = useMemo(() => getDiscoverySnapshot(window), [window]);
  const [selectedId, setSelectedId] = useState(DISCOVERY_HOT_TOPICS[0]?.id ?? "");
  const [observedTopicIds, setObservedTopicIds] = useState<string[]>(
    readObservedTopicIdsFromStorage,
  );
  const effectiveSelectedId = topics.some((topic) => topic.id === selectedId)
    ? selectedId
    : topics[0]?.id ?? "";
  const selectedTopic =
    topics.find((topic) => topic.id === effectiveSelectedId) ??
    topics[0] ??
    DISCOVERY_HOT_TOPICS[0];
  const selectedTopicObserved = selectedTopic ? observedTopicIds.includes(selectedTopic.id) : false;
  const observedTopics = useMemo(
    () => DISCOVERY_HOT_TOPICS.filter((topic) => observedTopicIds.includes(topic.id)),
    [observedTopicIds],
  );
  const actNowCount = DISCOVERY_OPPORTUNITIES.filter((item) => item.horizon === "act-now").length;

  useEffect(() => {
    const storage = getBrowserStorage();
    if (!storage) return;
    storage.setItem(
      OBSERVED_TOPICS_STORAGE_KEY,
      JSON.stringify(observedTopicIds),
    );
  }, [observedTopicIds]);

  const toggleObservedTopic = (topicId: string) => {
    setObservedTopicIds((current) =>
      current.includes(topicId)
        ? current.filter((id) => id !== topicId)
        : [...current, topicId],
    );
  };

  return (
    <div className="min-h-dvh overflow-hidden bg-[#050711] text-slate-100">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_8%_8%,rgba(56,189,248,0.18),transparent_28%),radial-gradient(circle_at_72%_0%,rgba(245,158,11,0.10),transparent_30%),radial-gradient(circle_at_80%_80%,rgba(16,185,129,0.10),transparent_32%)]" />
      <WorkbenchHeader query={query} onQueryChange={setQuery} />
      <div className="grid min-h-[calc(100dvh-64px)] grid-cols-1 lg:grid-cols-[264px_minmax(0,1fr)_392px]">
        <Sidebar actNowCount={actNowCount} observedTopics={observedTopics} />
        <main className="min-w-0 border-x border-white/10 bg-white/[0.025]">
          <div className="h-full overflow-y-auto px-4 py-4 sm:px-6 lg:px-7">
            <MobileSearchBar query={query} onQueryChange={setQuery} />
            <TopIntelligenceStrip snapshot={snapshot} />
            <section className="mt-5 overflow-hidden rounded-[28px] border border-white/10 bg-slate-950/70 shadow-2xl shadow-black/30 backdrop-blur-xl">
              <div className="border-b border-white/10 p-4 sm:p-5">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                  <div>
                    <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs font-medium text-cyan-100">
                      <Activity className="size-3.5" />
                      多源研究趋势情报
                    </div>
                    <h1 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-white sm:text-4xl">
                      AI 研究趋势情报系统
                    </h1>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                      从论文、开源项目、产品发布、benchmark、workshop 与社区讨论中识别热点，判断红海程度，并把高价值方向沉淀为可进入 RH 深挖的研究机会。
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {windowTabs.map((tab) => (
                      <button
                        key={tab.id}
                        type="button"
                        onClick={() => setWindow(tab.id)}
                        className={cn(
                          "rounded-2xl border px-4 py-3 text-left transition",
                          window === tab.id
                            ? "border-cyan-300/40 bg-cyan-300/15 text-cyan-50 shadow-lg shadow-cyan-950/40"
                            : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:bg-white/[0.06] hover:text-white",
                        )}
                      >
                        <div className="text-sm font-semibold">{tab.label}</div>
                        <div className="mt-1 text-[11px] text-slate-500">{tab.hint}</div>
                      </button>
                    ))}
                  </div>
                </div>
                <WindowBrief
                  className="mt-5"
                  query={query}
                  resultCount={topics.length}
                  sourceFilter={sourceFilter}
                  topics={topics}
                  window={window}
                />
              </div>

              <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_320px]">
                <div className="p-4 sm:p-5">
                  <SourceFocusBar
                    active={sourceFilter}
                    onChange={setSourceFilter}
                    topics={windowTopics}
                  />
                  <ActiveFilterStrip
                    query={query}
                    resultCount={topics.length}
                    sourceFilter={sourceFilter}
                    onClearQuery={() => setQuery("")}
                    onResetAll={() => {
                      setQuery("");
                      setSourceFilter("all");
                      setWindow("today");
                    }}
                    window={window}
                  />
                  <MobileSelectedTopicBrief
                    isObserved={selectedTopicObserved}
                    onToggleObserved={toggleObservedTopic}
                    topic={selectedTopic}
                  />
                  <div className="mb-4 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-white">
                      <Flame className="size-4 text-orange-300" />
                      {windowTabs.find((tab) => tab.id === window)?.label}榜
                    </div>
                    <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-400 sm:flex">
                      <Filter className="size-3.5" />
                      CS / AI Agent / Systems / Multimodal
                    </div>
                  </div>
                  {topics.length === 0 ? (
                    <EmptyTopicState
                      query={query}
                      onReset={() => {
                        setQuery("");
                        setSourceFilter("all");
                      }}
                    />
                  ) : (
                    <div className="space-y-3">
                      {topics.map((topic, index) => (
                        <HotTopicCard
                          key={topic.id}
                          topic={topic}
                          rank={index + 1}
                          selected={selectedTopic?.id === topic.id}
                          onSelect={() => setSelectedId(topic.id)}
                        />
                      ))}
                    </div>
                  )}
                </div>

                <div className="border-t border-white/10 bg-black/15 p-4 sm:p-5 xl:border-l xl:border-t-0">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-semibold text-white">趋势象限</div>
                    <div className="text-xs text-slate-500">影响潜力 × 拥挤度</div>
                  </div>
                  <MiniQuadrant selectedId={selectedTopic?.id} topics={topics} onSelect={setSelectedId} />
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <MetricTile label="平均热度" value={`${Math.round(topics.reduce((sum, t) => sum + t.heatScore, 0) / Math.max(1, topics.length))}`} suffix="/100" />
                    <MetricTile label="机会候选" value={`${topics.filter((t) => t.opportunityScore >= 78).length}`} suffix="个" />
                    <MetricTile label="黄海/蓝海" value={`${topics.filter((t) => t.ocean !== "red").length}`} suffix="个" />
                    <MetricTile label="多源信号" value={`${topics.reduce((sum, t) => sum + getTotalSignalCount(t), 0)}`} suffix="条" />
                  </div>
                </div>
              </div>
            </section>

            <section className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
              <TriageBoard topics={DISCOVERY_HOT_TOPICS} />
              <SourceHealthPanel />
            </section>
          </div>
        </main>
        <EvidencePanel
          isObserved={selectedTopicObserved}
          onToggleObserved={toggleObservedTopic}
          onResetFilters={() => {
            setQuery("");
            setSourceFilter("all");
          }}
          query={query}
          topic={selectedTopic}
        />
      </div>
    </div>
  );
}

function WorkbenchHeader({
  onQueryChange,
  query,
}: {
  onQueryChange: (value: string) => void;
  query: string;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#050711]/88 backdrop-blur-2xl">
      <div className="flex h-16 items-center gap-4 px-4 sm:px-6 lg:px-7">
        <Link href="/discovery" className="flex shrink-0 items-center gap-3">
          <div className="relative flex size-10 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-300 via-sky-300 to-emerald-300 text-slate-950 shadow-lg shadow-cyan-950/50">
            <Compass className="size-5" />
            <div className="absolute inset-0 rounded-2xl ring-1 ring-white/40" />
          </div>
          <div>
            <div className="text-sm font-semibold leading-none text-white">Discovery 发现</div>
            <div className="mt-1 text-[11px] text-slate-500">研究机会情报工作台</div>
          </div>
        </Link>
        <DiscoveryProductNav />
        <label className="hidden max-w-2xl flex-1 items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-500 shadow-inner transition focus-within:border-cyan-300/30 focus-within:bg-white/[0.06] md:flex">
          <Search className="size-4" />
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="搜索方向、论文、repo、benchmark 或产品发布..."
            className="w-full bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
            aria-label="搜索方向、论文、repo、benchmark 或产品发布"
          />
        </label>
        <div className="ml-auto flex items-center gap-2">
          <div className="hidden rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1.5 text-xs text-emerald-100 sm:block">
            今日已更新 · {DISCOVERY_LAST_UPDATED}
          </div>
          <Link
            href="/discover/issues/2026-05-10-weekly"
            className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-slate-300 transition hover:border-white/30 hover:bg-white/[0.08] hover:text-white"
          >
            已发布简报
          </Link>
        </div>
      </div>
    </header>
  );
}

function MobileSearchBar({
  onQueryChange,
  query,
}: {
  onQueryChange: (value: string) => void;
  query: string;
}) {
  return (
    <label className="mb-4 flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-3 text-sm text-slate-500 shadow-inner transition focus-within:border-cyan-300/30 focus-within:bg-white/[0.06] md:hidden">
      <Search className="size-4" />
      <input
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="搜索方向、论文、repo、benchmark..."
        className="w-full bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
        aria-label="移动端搜索方向、论文、repo、benchmark 或产品发布"
      />
    </label>
  );
}

function Sidebar({
  actNowCount,
  observedTopics,
}: {
  actNowCount: number;
  observedTopics: DiscoveryHotTopic[];
}) {
  return (
    <aside className="hidden min-h-0 bg-black/20 lg:block">
      <div className="flex h-[calc(100dvh-64px)] flex-col overflow-y-auto p-4">
        <div className="rounded-[24px] border border-white/10 bg-white/[0.035] p-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                type="button"
                className={cn(
                  "mb-1 flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left text-sm transition last:mb-0",
                  item.active
                    ? "bg-cyan-300/12 text-cyan-50 ring-1 ring-cyan-300/20"
                    : "text-slate-400 hover:bg-white/[0.05] hover:text-white",
                )}
              >
                <Icon className="size-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-4 rounded-[24px] border border-white/10 bg-white/[0.035] p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <Bell className="size-4 text-cyan-200" />
            观察列表
          </div>
          <div className="mt-3 rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.06] p-3">
            <div className="flex items-center justify-between text-xs text-cyan-100">
              <span>我的热点</span>
              <span>{observedTopics.length} 个</span>
            </div>
            <div className="mt-2 space-y-1.5">
              {observedTopics.length === 0 ? (
                <div className="text-xs leading-5 text-slate-500">
                  在右侧证据面板点击“加入观察列表”后，这里会显示你关注的热点。
                </div>
              ) : (
                observedTopics.slice(0, 3).map((topic) => (
                  <div key={topic.id} className="rounded-xl bg-black/20 px-2.5 py-2">
                    <div className="line-clamp-1 text-xs font-medium text-white">{topic.shortTitle}</div>
                    <div className="mt-1 text-[11px] text-slate-500">{topic.oceanLabel} · 机会 {topic.opportunityScore}</div>
                  </div>
                ))
              )}
            </div>
          </div>
          <div className="mt-3 space-y-3">
            {DISCOVERY_WATCHLISTS.map((watchlist) => (
              <div key={watchlist.name} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                <div className="text-sm font-medium text-slate-100">{watchlist.name}</div>
                <div className="mt-1 text-xs leading-5 text-slate-500">{watchlist.description}</div>
                <div className="mt-2 text-[11px] text-cyan-200">{watchlist.cadence}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-4 rounded-[24px] border border-white/10 bg-gradient-to-br from-cyan-300/14 to-violet-400/10 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-100/70">机会池</div>
          <div className="mt-3 text-4xl font-semibold text-white">{actNowCount}</div>
          <div className="mt-1 text-sm text-slate-400">个方向建议立即开工</div>
          <Link href="/discovery/opportunities/security-policy-and-auditing-for-tool-using-ai-agents" className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-cyan-100">
            查看首选机会 <ArrowRight className="size-4" />
          </Link>
        </div>
      </div>
    </aside>
  );
}

function TopIntelligenceStrip({ snapshot }: { snapshot: ReturnType<typeof getDiscoverySnapshot> }) {
  const yellowBlueCount = DISCOVERY_HOT_TOPICS.filter(
    (topic) => topic.ocean === "yellow" && topic.oceanLabel.includes("蓝"),
  ).length;
  const redEdgeCount = DISCOVERY_HOT_TOPICS.filter(
    (topic) => topic.ocean === "red" || topic.oceanLabel.includes("红"),
  ).length;
  return (
    <section className="grid gap-3 md:grid-cols-4">
      <KpiCard label="当前窗口信号" value={`${snapshot.signalCount}`} note="跨 6 类来源" tone="cyan" />
      <KpiCard label="可推进候选" value={`${snapshot.opportunityCandidateCount}`} note={`${snapshot.topicCount} 个热点中筛出`} tone="violet" />
      <KpiCard label="黄海偏蓝" value={`${yellowBlueCount}`} note="优先进入 RH" tone="emerald" />
      <KpiCard label="红海边缘" value={`${redEdgeCount}`} note="需避开同质化" tone="rose" />
    </section>
  );
}

function KpiCard({ label, value, note, tone }: { label: string; value: string; note: string; tone: "cyan" | "violet" | "emerald" | "rose" }) {
  const toneClass = {
    cyan: "from-cyan-300/16 to-sky-400/5 text-cyan-100",
    violet: "from-amber-300/14 to-orange-400/5 text-amber-100",
    emerald: "from-emerald-300/20 to-teal-400/5 text-emerald-100",
    rose: "from-rose-300/20 to-orange-400/5 text-rose-100",
  }[tone];
  return (
    <div className={cn("rounded-[22px] border border-white/10 bg-gradient-to-br p-4 shadow-lg shadow-black/20", toneClass)}>
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-2 flex items-end justify-between gap-3">
        <div className="text-3xl font-semibold tracking-tight text-white">{value}</div>
        <Sparkles className="size-4 opacity-70" />
      </div>
      <div className="mt-2 text-xs text-slate-500">{note}</div>
    </div>
  );
}

function WindowBrief({
  className,
  query,
  resultCount,
  sourceFilter,
  topics,
  window,
}: {
  className?: string;
  query: string;
  resultCount: number;
  sourceFilter: SourceFilter;
  topics: DiscoveryHotTopic[];
  window: DiscoveryWindow;
}) {
  const topTopic = topics[0];
  const windowLabel = windowTabs.find((tab) => tab.id === window)?.label ?? "当前窗口";
  const focusLabel = sourceFilters.find((source) => source.key === sourceFilter)?.label ?? "全来源";

  return (
    <div className={cn("grid gap-3 xl:grid-cols-[1.1fr_0.9fr_0.9fr]", className)}>
      <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/[0.07] p-4">
        <div className="flex items-center gap-2 text-xs font-medium text-cyan-100">
          <RadioTower className="size-3.5" />
          {windowLabel} · {focusLabel}
        </div>
        <p className="mt-2 text-sm leading-6 text-cyan-50/85">
          {topTopic
            ? `首要热点是「${topTopic.title}」，机会分 ${topTopic.opportunityScore}，当前判断为 ${topTopic.oceanLabel}。`
            : "当前窗口暂无热点。"}
        </p>
        {query ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-black/15 px-3 py-1 text-[11px] text-cyan-100/80">
              当前搜索：{query}
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/15 px-3 py-1 text-[11px] text-slate-300">
              命中 {resultCount} 个热点
            </div>
          </div>
        ) : null}
      </div>
      <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
          <Route className="size-3.5 text-emerald-200" />
          进入条件
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          只把“多源共振 + 拥挤度可控 + 72 小时可验证”的方向转入 RH，避免研究资源被热点噪音吞掉。
        </p>
      </div>
      <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
          <ShieldCheck className="size-3.5 text-amber-200" />
          规避策略
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          红海边缘方向不直接做排行榜；必须改成失败审计、机制解释或数据可得的窄问题。
        </p>
      </div>
    </div>
  );
}

function ActiveFilterStrip({
  onClearQuery,
  onResetAll,
  query,
  resultCount,
  sourceFilter,
  window,
}: {
  onClearQuery: () => void;
  onResetAll: () => void;
  query: string;
  resultCount: number;
  sourceFilter: SourceFilter;
  window: DiscoveryWindow;
}) {
  const sourceLabel = sourceFilters.find((item) => item.key === sourceFilter)?.label ?? "全来源";
  const windowLabel = windowTabs.find((item) => item.id === window)?.label ?? "当前窗口";

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-[22px] border border-white/10 bg-white/[0.03] p-3">
      <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1 text-[11px] text-slate-300">
        <Filter className="size-3.5" />
        {windowLabel}
      </div>
      <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1 text-[11px] text-slate-300">
        来源：{sourceLabel}
      </div>
      {query ? (
        <button
          type="button"
          onClick={onClearQuery}
          className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-[11px] text-cyan-100 transition hover:border-cyan-300/35 hover:bg-cyan-300/15"
        >
          搜索：{query}
          <span className="text-cyan-200/80">清空</span>
        </button>
      ) : null}
      <div className="ml-auto inline-flex items-center gap-2 rounded-full border border-emerald-300/15 bg-emerald-300/10 px-3 py-1 text-[11px] text-emerald-100">
        命中 {resultCount} 个热点
      </div>
      <button
        type="button"
        onClick={onResetAll}
        className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1 text-[11px] text-slate-300 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
      >
        重置全部
      </button>
    </div>
  );
}

function SourceFocusBar({
  active,
  onChange,
  topics,
}: {
  active: SourceFilter;
  onChange: (source: SourceFilter) => void;
  topics: DiscoveryHotTopic[];
}) {
  const countFor = (source: SourceFilter) => {
    if (source === "all") {
      return topics.reduce((sum, topic) => sum + getTotalSignalCount(topic), 0);
    }

    return topics.reduce((sum, topic) => sum + topic.sourceCounts[source], 0);
  };

  return (
    <div className="mb-4 rounded-[22px] border border-white/10 bg-black/20 p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <SlidersHorizontal className="size-4 text-cyan-200" />
          信号来源聚焦
        </div>
        <div className="hidden text-xs text-slate-500 sm:block">筛选后仍按热度与来源强度排序</div>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {sourceFilters.map((source) => {
          const selected = active === source.key;
          return (
            <button
              key={source.key}
              type="button"
              onClick={() => onChange(source.key)}
              className={cn(
                "min-w-[108px] rounded-2xl border px-3 py-2 text-left transition",
                selected
                  ? "border-cyan-300/40 bg-cyan-300/15 text-cyan-50"
                  : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/25 hover:bg-white/[0.06] hover:text-white",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold">{source.label}</span>
                <span className="font-mono text-[11px] text-slate-500">{countFor(source.key)}</span>
              </div>
              <div className="mt-1 text-[11px] text-slate-500">{source.hint}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function EmptyTopicState({
  onReset,
  query,
}: {
  onReset: () => void;
  query: string;
}) {
  return (
    <div className="rounded-[24px] border border-dashed border-white/10 bg-black/20 p-6">
      <div className="max-w-lg">
        <div className="text-sm font-semibold text-white">没有匹配的热点</div>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          {query
            ? `当前搜索“${query}”没有命中现有热点，可以清空搜索或切回全来源后再看。`
            : "当前筛选条件下没有可展示的热点，可以切回全来源查看完整榜单。"}
        </p>
        <button
          type="button"
          onClick={onReset}
          className="mt-4 inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-white/25 hover:bg-white/[0.07]"
        >
          重置筛选
          <ArrowRight className="size-4" />
        </button>
      </div>
    </div>
  );
}

function MobileSelectedTopicBrief({
  isObserved,
  onToggleObserved,
  topic,
}: {
  isObserved: boolean;
  onToggleObserved: (topicId: string) => void;
  topic?: DiscoveryHotTopic;
}) {
  if (!topic) return null;
  const oceanMeta = DISCOVERY_OCEAN_META[topic.ocean];

  return (
    <section className="mb-4 rounded-[24px] border border-white/10 bg-white/[0.035] p-4 lg:hidden">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">当前选中热点</div>
          <h2 className="mt-2 text-lg font-semibold tracking-tight text-white">{topic.shortTitle}</h2>
        </div>
        <span className={cn("rounded-full border px-2.5 py-1 text-xs", oceanMeta.color)}>{topic.oceanLabel}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-400">{topic.summary}</p>
      <div className="mt-4 grid grid-cols-3 gap-2">
        <MobileBriefMetric label="机会分" value={topic.opportunityScore} />
        <MobileBriefMetric label="热度" value={topic.heatScore} />
        <MobileBriefMetric label="动量" suffix="%" value={topic.momentumDelta} />
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        <a
          href="#discovery-evidence-panel"
          className="inline-flex items-center justify-center gap-2 rounded-2xl bg-cyan-200 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100"
        >
          查看完整证据
          <ArrowRight className="size-4" />
        </a>
        <a
          href="#evidence-panel-action"
          className="inline-flex items-center justify-center gap-2 rounded-2xl border border-emerald-300/30 bg-emerald-300/10 px-4 py-3 text-sm font-semibold text-emerald-50 transition hover:border-emerald-200/60 hover:bg-emerald-300/15"
        >
          直达建议动作
          <ArrowRight className="size-4" />
        </a>
        <button
          type="button"
          onClick={() => onToggleObserved(topic.id)}
          className={cn(
            "rounded-2xl border px-4 py-3 text-sm font-medium transition",
            isObserved
              ? "border-cyan-300/35 bg-cyan-300/15 text-cyan-50"
              : "border-white/10 bg-white/[0.04] text-slate-200 hover:border-white/25 hover:bg-white/[0.07]",
          )}
        >
          {isObserved ? "已加入观察" : "加入观察列表"}
        </button>
      </div>
    </section>
  );
}

function MobileBriefMetric({
  label,
  value,
  suffix = "",
}: {
  label: string;
  value: number;
  suffix?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="mt-2 text-lg font-semibold text-white">
        {value}
        <span className="ml-0.5 text-xs text-slate-500">{suffix}</span>
      </div>
    </div>
  );
}

function HotTopicCard({ topic, rank, selected, onSelect }: { topic: DiscoveryHotTopic; rank: number; selected: boolean; onSelect: () => void }) {
  const oceanMeta = DISCOVERY_OCEAN_META[topic.ocean];
  const totalSignals = getTotalSignalCount(topic);
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-label={`选择热点 ${topic.title}`}
      className={cn(
        "group w-full rounded-[24px] border p-4 text-left transition duration-200",
        selected
          ? "border-cyan-300/40 bg-cyan-300/[0.08] shadow-2xl shadow-cyan-950/30"
          : "border-white/10 bg-white/[0.035] hover:border-white/20 hover:bg-white/[0.06]",
      )}
    >
      <div className="flex items-start gap-4">
        <div className={cn("flex size-10 shrink-0 items-center justify-center rounded-2xl font-mono text-sm font-semibold", selected ? "bg-cyan-200 text-slate-950" : "bg-white/10 text-slate-300")}>
          {String(rank).padStart(2, "0")}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-slate-300">{topic.category}</span>
            <span className={cn("rounded-full border px-2.5 py-1 text-xs", oceanMeta.color)}>{topic.oceanLabel}</span>
            <span className="rounded-full border border-orange-300/20 bg-orange-300/10 px-2.5 py-1 text-xs text-orange-100">+{topic.momentumDelta}%</span>
          </div>
          <div className="mt-3 flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-white">{topic.title}</h2>
              <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-400">{topic.summary}</p>
            </div>
            <ChevronRight className={cn("mt-1 size-5 shrink-0 transition", selected ? "text-cyan-200" : "text-slate-600 group-hover:text-slate-300")} />
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_150px]">
            <div>
              <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
                <span>多源信号 {totalSignals} 条</span>
                <span>机会分 {topic.opportunityScore}</span>
              </div>
              <SourceDistribution topic={topic} />
            </div>
            <TrendSparkline values={topic.trendline} />
          </div>
        </div>
      </div>
    </button>
  );
}

function SourceDistribution({ topic }: { topic: DiscoveryHotTopic }) {
  const total = getTotalSignalCount(topic);
  return (
    <div className="space-y-2">
      <div className="flex h-2 overflow-hidden rounded-full bg-white/10">
        {sourceLabels.map((source, index) => {
          const width = `${(topic.sourceCounts[source.key] / Math.max(1, total)) * 100}%`;
          const colors = ["bg-cyan-300", "bg-sky-300", "bg-emerald-300", "bg-amber-300", "bg-rose-300", "bg-slate-300"];
          return <div key={source.key} className={colors[index]} style={{ width }} />;
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        {sourceLabels.map((source) => (
          <span key={source.key} className="rounded-full bg-white/[0.04] px-2 py-0.5 text-[11px] text-slate-500">
            {source.label} {topic.sourceCounts[source.key]}
          </span>
        ))}
      </div>
    </div>
  );
}

function TrendSparkline({ values }: { values: number[] }) {
  const max = Math.max(...values, 1);
  return (
    <div className="flex h-20 items-end gap-1.5 rounded-2xl border border-white/10 bg-black/20 px-3 py-2">
      {values.map((value, index) => (
        <div key={`${value}-${index}`} className="flex flex-1 items-end">
          <div
            className="w-full rounded-t-md bg-gradient-to-t from-cyan-500 to-cyan-200 opacity-80"
            style={{ height: `${Math.max(14, (value / max) * 100)}%` }}
            title={`${value}`}
          />
        </div>
      ))}
    </div>
  );
}

function MiniQuadrant({ topics, selectedId, onSelect }: { topics: DiscoveryHotTopic[]; selectedId?: string; onSelect: (id: string) => void }) {
  return (
    <div className="relative mt-4 h-72 overflow-hidden rounded-[24px] border border-white/10 bg-[radial-gradient(circle_at_20%_20%,rgba(34,211,238,0.12),transparent_28%),radial-gradient(circle_at_80%_20%,rgba(16,185,129,0.08),transparent_24%),linear-gradient(135deg,rgba(15,23,42,0.9),rgba(2,6,23,0.96))]">
      <div className="absolute inset-8 rounded-2xl border border-white/10" />
      <div className="absolute left-8 right-8 top-1/2 border-t border-dashed border-white/15" />
      <div className="absolute bottom-8 top-8 left-1/2 border-l border-dashed border-white/15" />
      <div className="absolute left-4 top-4 text-[10px] text-slate-500">高机会</div>
      <div className="absolute bottom-4 right-4 text-[10px] text-slate-500">更拥挤</div>
      {topics.map((topic, index) => {
        const active = selectedId === topic.id;
        return (
          <button
            key={topic.id}
            type="button"
            onClick={() => onSelect(topic.id)}
            className={cn(
              "absolute flex size-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border text-xs font-semibold transition",
              active
                ? "border-cyan-100 bg-cyan-200 text-slate-950 shadow-lg shadow-cyan-300/30"
                : "border-white/30 bg-white/12 text-white hover:bg-white/25",
            )}
            style={{ left: `${Math.max(12, Math.min(88, topic.saturation))}%`, top: `${Math.max(12, Math.min(88, 100 - topic.opportunityScore))}%` }}
            aria-label={`查看趋势象限 ${topic.title}`}
          >
            {index + 1}
          </button>
        );
      })}
    </div>
  );
}

function MetricTile({ label, value, suffix }: { label: string; value: string; suffix: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-3">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-2xl font-semibold text-white">{value}</span>
        <span className="text-xs text-slate-500">{suffix}</span>
      </div>
    </div>
  );
}

function TriageBoard({ topics }: { topics: DiscoveryHotTopic[] }) {
  const sorted = [...topics].sort((a, b) => b.opportunityScore - a.opportunityScore);
  const immediate = sorted.filter((topic) => topic.opportunityScore >= 86);
  const watch = sorted.filter((topic) => topic.opportunityScore < 86 && topic.opportunityScore >= 78);
  const crowded = sorted.filter((topic) => topic.saturation >= 55 || topic.oceanLabel.includes("红"));

  return (
    <div className="rounded-[28px] border border-white/10 bg-slate-950/70 p-5 shadow-xl shadow-black/25">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
            <Layers3 className="size-3.5 text-cyan-200" />
            情报处理队列
          </div>
          <h2 className="mt-3 text-xl font-semibold tracking-tight text-white">从热点收敛到可执行研究</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            不是把所有热门都推荐给用户，而是按“立即深挖 / 继续观察 / 红海规避”做产品化分流。
          </p>
        </div>
        <div className="rounded-2xl border border-emerald-300/20 bg-emerald-300/10 px-4 py-3 text-right">
          <div className="text-2xl font-semibold text-white">{immediate.length}</div>
          <div className="text-xs text-emerald-100/70">建议立即转 RH</div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <TriageLane
          icon={CheckCircle2}
          title="立即深挖"
          tone="emerald"
          topics={immediate}
          emptyText="暂无高置信机会"
        />
        <TriageLane
          icon={Eye}
          title="继续观察"
          tone="cyan"
          topics={watch}
          emptyText="暂无观察项"
        />
        <TriageLane
          icon={ShieldCheck}
          title="红海规避"
          tone="rose"
          topics={crowded}
          emptyText="暂无红海边缘"
        />
      </div>
    </div>
  );
}

function TriageLane({
  emptyText,
  icon: Icon,
  title,
  tone,
  topics,
}: {
  emptyText: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  tone: "emerald" | "cyan" | "rose";
  topics: DiscoveryHotTopic[];
}) {
  const toneClass = {
    emerald: "text-emerald-100 bg-emerald-300/10 border-emerald-300/20",
    cyan: "text-cyan-100 bg-cyan-300/10 border-cyan-300/20",
    rose: "text-rose-100 bg-rose-300/10 border-rose-300/20",
  }[tone];

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
      <div className={cn("inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs", toneClass)}>
        <Icon className="size-3.5" />
        {title}
      </div>
      <div className="mt-3 space-y-2">
        {topics.length === 0 ? (
          <div className="rounded-xl bg-black/20 p-3 text-xs text-slate-500">{emptyText}</div>
        ) : (
          topics.slice(0, 3).map((topic) => (
            <div key={topic.id} className="rounded-xl border border-white/10 bg-black/20 p-3">
              <div className="line-clamp-1 text-sm font-medium text-white">{topic.shortTitle}</div>
              <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
                <span>{topic.oceanLabel}</span>
                <span>机会 {topic.opportunityScore}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function SourceHealthPanel() {
  return (
    <div className="rounded-[28px] border border-white/10 bg-slate-950/70 p-5 shadow-xl shadow-black/25">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
            <Database className="size-3.5 text-violet-200" />
            来源健康
          </div>
          <h2 className="mt-3 text-xl font-semibold tracking-tight text-white">多源信号面板</h2>
        </div>
        <div className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-400">
          {DISCOVERY_LAST_UPDATED}
        </div>
      </div>
      <div className="mt-4 space-y-3">
        {DISCOVERY_SOURCE_STATUS.map((source) => (
          <div key={source.name} className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-white">{source.name}</div>
                <div className="mt-1 text-xs leading-5 text-slate-500">{source.label}</div>
              </div>
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[11px]",
                  source.status === "稳定" && "border-emerald-300/20 bg-emerald-300/10 text-emerald-100",
                  source.status === "观察中" && "border-cyan-300/20 bg-cyan-300/10 text-cyan-100",
                  source.status === "需复核" && "border-amber-300/20 bg-amber-300/10 text-amber-100",
                )}
              >
                {source.status}
              </span>
            </div>
            <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500">
              <span>{source.cadence}刷新 · {source.lastSync}</span>
              <span>{source.signalCount} 条信号</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidencePanel({
  isObserved,
  onToggleObserved,
  onResetFilters,
  query,
  topic,
}: {
  isObserved: boolean;
  onToggleObserved: (topicId: string) => void;
  onResetFilters: () => void;
  query: string;
  topic?: DiscoveryHotTopic;
}) {
  if (!topic) {
    return (
      <aside className="bg-black/25 lg:min-h-0">
        <div className="p-4 lg:h-[calc(100dvh-64px)] lg:overflow-y-auto lg:p-5">
          <div className="rounded-[28px] border border-white/10 bg-slate-950/80 p-5 shadow-2xl shadow-black/30 backdrop-blur-xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
              <CircleDot className="size-3.5 text-cyan-200" />
              当前热点
            </div>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">暂无可展示热点</h2>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              {query
                ? `搜索“${query}”后没有留下可展示的趋势项。`
                : "当前筛选条件没有留下可展示的趋势项。"}
            </p>
            <button
              type="button"
              onClick={onResetFilters}
              className="mt-5 inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-medium text-slate-200 transition hover:border-white/25 hover:bg-white/[0.07]"
            >
              重置筛选
              <ArrowRight className="size-4" />
            </button>
          </div>
        </div>
      </aside>
    );
  }
  const oceanMeta = DISCOVERY_OCEAN_META[topic.ocean];
  const matchedTags = getMatchedTags(topic, query);
  const opportunity = topic.opportunitySlug ? getOpportunity(topic.opportunitySlug) : undefined;
  const handoffHref = opportunity ? buildNewTopicHrefFromDiscoverBrief(opportunity.brief) : null;

  return (
    <aside id="discovery-evidence-panel" className="bg-black/25 lg:min-h-0">
      <div className="p-4 lg:h-[calc(100dvh-64px)] lg:overflow-y-auto lg:p-5">
        <div className="rounded-[28px] border border-white/10 bg-slate-950/80 p-5 shadow-2xl shadow-black/30 backdrop-blur-xl">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
                <CircleDot className="size-3.5 text-cyan-200" />
                当前热点
              </div>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">{topic.shortTitle}</h2>
            </div>
            <span className={cn("rounded-full border px-3 py-1 text-xs", oceanMeta.color)}>{topic.oceanLabel}</span>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-400">{topic.whyHot}</p>

          <EvidenceSectionNav />

          <div className="mt-5 grid grid-cols-2 gap-3">
            <PanelMetric icon={Flame} label="热度" value={topic.heatScore} />
            <PanelMetric icon={Zap} label="动量" value={topic.momentumDelta} suffix="%" />
            <PanelMetric icon={Sparkles} label="新鲜度" value={topic.freshness} />
            <PanelMetric icon={Boxes} label="拥挤度" value={topic.saturation} />
          </div>

          <div id="evidence-panel-decision">
            <DecisionStack topic={topic} />
          </div>

          <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.035] p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <ShieldCheck className="size-4 text-emerald-200" />
              海域判断
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-400">{topic.oceanRationale}</p>
          </div>

          <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.035] p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <Target className="size-4 text-cyan-200" />
              可研究问题
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-300">{topic.researchQuestion}</p>
          </div>

          {(matchedTags.length > 0 || query) && (
            <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.035] p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Search className="size-4 text-cyan-200" />
                当前命中线索
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                {matchedTags.length > 0
                  ? `当前搜索优先命中了该热点的这些标签：${matchedTags.join("、")}。`
                  : `当前搜索“${query}”命中了该热点的标题、摘要或研究问题。`}
              </p>
            </div>
          )}

          <div id="evidence-panel-evidence" className="mt-5">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Newspaper className="size-4 text-violet-200" />
                证据链
              </div>
              <span className="text-xs text-slate-500">{topic.evidence.length} 条精选</span>
            </div>
            <div className="space-y-3">
              {topic.evidence.map((item) => (
                <a key={`${item.title}-${item.date}`} href={item.url} target="_blank" rel="noreferrer" className="block rounded-2xl border border-white/10 bg-black/20 p-3 transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.04]">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[11px] text-slate-400">{sourceKindLabel(item.kind)}</span>
                        <span className="font-mono text-[11px] text-slate-600">{item.date}</span>
                      </div>
                      <div className="mt-2 text-sm font-medium leading-5 text-white">{item.title}</div>
                    </div>
                    <ChevronRight className="mt-1 size-4 shrink-0 text-slate-600" />
                  </div>
                  <p className="mt-2 text-xs leading-5 text-slate-500">{item.takeaway}</p>
                </a>
              ))}
            </div>
          </div>

          <div className="mt-5 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-amber-100">
              <BarChart3 className="size-4" />
              反向信号 / 风险
            </div>
            <ul className="mt-2 space-y-2 text-sm leading-6 text-amber-50/75">
              {topic.contrarianSignals.map((signal) => (
                <li key={signal} className="flex gap-2">
                  <span className="mt-2 size-1.5 shrink-0 rounded-full bg-amber-200" />
                  <span>{signal}</span>
                </li>
              ))}
            </ul>
          </div>

          <div id="evidence-panel-action" className="mt-5 space-y-3">
            <div className="text-sm font-semibold text-white">建议动作</div>
            <p className="text-sm leading-6 text-slate-400">{topic.recommendedAction}</p>
            <div className="grid gap-2">
              {topic.opportunitySlug && (
                <Link href={`/discovery/opportunities/${topic.opportunitySlug}`} className="inline-flex items-center justify-center gap-2 rounded-2xl bg-cyan-200 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100">
                  查看机会详情 <ArrowRight className="size-4" />
                </Link>
              )}
              {handoffHref && (
                <Link href={handoffHref} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-emerald-300/30 bg-emerald-300/10 px-4 py-3 text-sm font-semibold text-emerald-50 transition hover:border-emerald-200/60 hover:bg-emerald-300/15">
                  创建 RH Topic <ArrowRight className="size-4" />
                </Link>
              )}
              <button
                type="button"
                onClick={() => onToggleObserved(topic.id)}
                className={cn(
                  "rounded-2xl border px-4 py-3 text-sm font-medium transition",
                  isObserved
                    ? "border-cyan-300/35 bg-cyan-300/15 text-cyan-50"
                    : "border-white/10 bg-white/[0.04] text-slate-200 hover:border-white/25 hover:bg-white/[0.07]",
                )}
              >
                {isObserved ? "已加入观察" : "加入观察列表"}
              </button>
            </div>
          </div>
        </div>

        <div className="sticky bottom-0 z-20 mt-4 grid gap-2 rounded-[24px] border border-white/10 bg-[#050711]/92 p-3 shadow-2xl shadow-black/40 backdrop-blur-xl lg:hidden">
          <div className="flex items-center justify-between gap-3 text-xs text-slate-400">
            <span className="line-clamp-1">{topic.shortTitle}</span>
            <span className="font-mono text-cyan-100">{topic.opportunityScore}/100</span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {topic.opportunitySlug ? (
              <Link
                href={`/discovery/opportunities/${topic.opportunitySlug}`}
                className="inline-flex items-center justify-center rounded-2xl bg-cyan-200 px-3 py-2.5 text-xs font-semibold text-slate-950"
              >
                机会详情
              </Link>
            ) : (
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-center text-xs text-slate-500">
                无详情页
              </div>
            )}
            {handoffHref ? (
              <Link
                href={handoffHref}
                className="inline-flex items-center justify-center rounded-2xl border border-emerald-300/30 bg-emerald-300/10 px-3 py-2.5 text-xs font-semibold text-emerald-50"
              >
                创建 Topic
              </Link>
            ) : (
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-center text-xs text-slate-500">
                无交接
              </div>
            )}
            <button
              type="button"
              onClick={() => onToggleObserved(topic.id)}
              className={cn(
                "rounded-2xl px-3 py-2.5 text-xs font-semibold transition",
                isObserved
                  ? "border border-cyan-300/35 bg-cyan-300/15 text-cyan-50"
                  : "border border-white/10 bg-white/[0.04] text-slate-200",
              )}
            >
              {isObserved ? "已观察" : "观察"}
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}

function EvidenceSectionNav() {
  const items = [
    { href: "#evidence-panel-decision", label: "判断" },
    { href: "#evidence-panel-evidence", label: "证据" },
    { href: "#evidence-panel-action", label: "动作" },
  ];

  return (
    <div className="mt-4 flex gap-2 overflow-x-auto pb-1 lg:hidden">
      {items.map((item) => (
        <a
          key={item.href}
          href={item.href}
          className="inline-flex shrink-0 items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] text-slate-300 transition hover:border-white/20 hover:bg-white/[0.06] hover:text-white"
        >
          {item.label}
        </a>
      ))}
    </div>
  );
}

function DecisionStack({ topic }: { topic: DiscoveryHotTopic }) {
  const supportCount = topic.evidence.filter((item) => item.stance === "support").length;
  const riskCount = topic.evidence.filter((item) => item.stance === "risk").length;
  const decisionScore = Math.round(
    topic.opportunityScore * 0.52 +
      topic.freshness * 0.2 +
      (100 - topic.saturation) * 0.18 +
      Math.min(10, supportCount * 2),
  );

  return (
    <div className="mt-5 rounded-2xl border border-cyan-300/20 bg-cyan-300/[0.06] p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <BarChart3 className="size-4 text-cyan-200" />
          进入指数
        </div>
        <div className="font-mono text-sm text-cyan-100">{decisionScore}/100</div>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-sky-300 to-emerald-300"
          style={{ width: `${Math.min(100, decisionScore)}%` }}
        />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-xl bg-black/20 p-2">
          <div className="text-sm font-semibold text-white">{supportCount}</div>
          <div className="mt-1 text-[11px] text-slate-500">支撑证据</div>
        </div>
        <div className="rounded-xl bg-black/20 p-2">
          <div className="text-sm font-semibold text-white">{riskCount}</div>
          <div className="mt-1 text-[11px] text-slate-500">风险证据</div>
        </div>
        <div className="rounded-xl bg-black/20 p-2">
          <div className="text-sm font-semibold text-white">{topic.contrarianSignals.length}</div>
          <div className="mt-1 text-[11px] text-slate-500">反向信号</div>
        </div>
      </div>
    </div>
  );
}

function PanelMetric({ icon: Icon, label, value, suffix = "" }: { icon: React.ComponentType<{ className?: string }>; label: string; value: number; suffix?: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-3">
      <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
        <Icon className="size-3.5" />
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold text-white">
        {value}<span className="text-sm text-slate-500">{suffix}</span>
      </div>
    </div>
  );
}

function sourceKindLabel(kind: string): string {
  const labels: Record<string, string> = {
    paper: "论文",
    repo: "开源",
    product: "产品",
    benchmark: "评测",
    workshop: "会议",
    community: "社区",
    blog: "博客",
  };
  return labels[kind] ?? kind;
}
