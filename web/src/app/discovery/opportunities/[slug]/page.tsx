import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Database,
  ExternalLink,
  FileText,
  GitBranch,
  Radar,
  Route,
  ShieldAlert,
  Sparkles,
  Target,
} from "lucide-react";
import { DISCOVERY_OPPORTUNITIES, getOpportunity, type DiscoveryOpportunity } from "@/lib/discovery-product";
import { buildNewTopicHrefFromDiscoverBrief } from "@/lib/topic-prefill";
import { cn } from "@/lib/utils";
import { DiscoveryProductNav } from "@/components/discovery/discovery-product-nav";
import { DiscoveryHandoffButton } from "@/components/discovery/discovery-handoff-button";

interface OpportunityPageProps {
  params: Promise<{ slug: string }>;
}

const scoreLabels: Array<{
  key: keyof DiscoveryOpportunity["radar"];
  label: string;
  description: string;
}> = [
  { key: "impact", label: "影响潜力", description: "是否值得投入研究资源" },
  { key: "momentum", label: "热度动量", description: "近期是否快速升温" },
  { key: "feasibility", label: "落地可行", description: "30 天内能否做出证据" },
  { key: "saturation", label: "拥挤度", description: "同质化竞争强度" },
];

export function generateStaticParams() {
  return DISCOVERY_OPPORTUNITIES.map((opportunity) => ({ slug: opportunity.slug }));
}

export async function generateMetadata({ params }: OpportunityPageProps): Promise<Metadata> {
  const { slug } = await params;
  const opportunity = getOpportunity(slug);
  if (!opportunity) {
    return { title: "未找到机会 — Discovery 发现" };
  }

  return {
    title: `${opportunity.title} — Discovery 发现`,
    description: opportunity.oneLiner,
  };
}

export default async function OpportunityDetailPage({ params }: OpportunityPageProps) {
  const { slug } = await params;
  const opportunity = getOpportunity(slug);
  if (!opportunity) notFound();

  const decisionLabel = opportunity.horizon === "act-now" ? "建议立即深挖" : "建议继续观察";
  const selectedGoalPreviewIds = opportunity.brief.goal_previews.map((goal) => goal.id);
  const enterScore = Math.round(
    opportunity.radar.impact * 0.32 +
      opportunity.radar.momentum * 0.26 +
      opportunity.radar.feasibility * 0.27 +
      (100 - opportunity.radar.saturation) * 0.15,
  );

  return (
    <div className="min-h-dvh overflow-hidden bg-[#050711] text-slate-100">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_8%_8%,rgba(56,189,248,0.20),transparent_30%),radial-gradient(circle_at_78%_0%,rgba(168,85,247,0.20),transparent_34%),radial-gradient(circle_at_76%_84%,rgba(16,185,129,0.12),transparent_34%)]" />
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#050711]/88 backdrop-blur-2xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
          <Link href="/discovery/track" className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-cyan-300/40 hover:bg-cyan-300/10 hover:text-cyan-50">
            <ArrowLeft className="size-4" />
            返回趋势雷达
          </Link>
          <DiscoveryProductNav />
          <Link href={buildNewTopicHrefFromDiscoverBrief(opportunity.brief)} className="inline-flex items-center gap-2 rounded-full bg-cyan-200 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100">
            转入 RH 深挖
            <ArrowRight className="size-4" />
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8">
        <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-stretch">
          <div className="rounded-[32px] border border-white/10 bg-slate-950/72 p-6 shadow-2xl shadow-black/30 backdrop-blur-xl lg:p-8">
            <div className="flex flex-wrap items-center gap-2">
              <Pill>{opportunity.category}</Pill>
              <Pill tone={opportunity.horizon === "act-now" ? "emerald" : "cyan"}>{decisionLabel}</Pill>
              {opportunity.audience.map((audience) => (
                <Pill key={audience} tone="muted">{audience}</Pill>
              ))}
            </div>
            <h1 className="mt-6 max-w-4xl text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
              {opportunity.title}
            </h1>
            <p className="mt-5 max-w-3xl text-base leading-8 text-slate-400 md:text-lg">
              {opportunity.oneLiner}
            </p>
            <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {scoreLabels.map((score) => (
                <ScoreCard
                  key={score.key}
                  description={score.description}
                  label={score.label}
                  value={opportunity.radar[score.key]}
                />
              ))}
            </div>
          </div>

          <aside className="rounded-[32px] border border-white/10 bg-slate-950/72 p-5 shadow-2xl shadow-black/30 backdrop-blur-xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs font-medium text-cyan-100">
              <Radar className="size-3.5" />
              方向判断
            </div>
            <div className="mt-5 rounded-2xl border border-cyan-300/20 bg-cyan-300/[0.06] p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-white">进入指数</div>
                <div className="font-mono text-sm text-cyan-100">{enterScore}/100</div>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-blue-300 to-violet-300" style={{ width: `${enterScore}%` }} />
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-400">{opportunity.productThesis}</p>
            </div>
            <div className="mt-4 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm leading-6 text-rose-50/80">
              <div className="mb-2 flex items-center gap-2 font-semibold text-rose-100">
                <ShieldAlert className="size-4" />
                反向观点 / 不该怎么做
              </div>
              {opportunity.counterPosition}
            </div>
          </aside>
        </section>

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-start">
          <div className="space-y-5">
            <DossierSection title="为什么现在" icon={Sparkles} eyebrow="Trend timing">
              <p className="text-base leading-8 text-slate-300">{opportunity.brief.why_now}</p>
            </DossierSection>

            <DossierSection title="信号时间线" icon={GitBranch} eyebrow="Evidence trail">
              <div className="space-y-3">
                {opportunity.signals.map((signal, index) => (
                  <a
                    key={`${signal.title}-${signal.date}`}
                    href={signal.url}
                    target="_blank"
                    rel="noreferrer"
                    className="group grid gap-3 rounded-2xl border border-white/10 bg-white/[0.035] p-4 transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.05] md:grid-cols-[120px_1fr]"
                  >
                    <div className="flex items-center gap-3 md:block">
                      <div className="flex size-8 items-center justify-center rounded-full bg-cyan-200 font-mono text-xs font-semibold text-slate-950">
                        {index + 1}
                      </div>
                      <div className="md:mt-3">
                        <div className="font-mono text-xs text-slate-500">{signal.date}</div>
                        <div className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">{sourceKindLabel(signal.kind)}</div>
                      </div>
                    </div>
                    <div>
                      <div className="flex items-start justify-between gap-3">
                        <h3 className="font-semibold text-white">{signal.title}</h3>
                        <ExternalLink className="size-4 shrink-0 text-slate-600 transition group-hover:text-cyan-100" />
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-400">{signal.takeaway}</p>
                    </div>
                  </a>
                ))}
              </div>
            </DossierSection>

            <DossierSection title="可写成论文的切口" icon={Target} eyebrow="Research angles">
              <div className="grid gap-3 md:grid-cols-3">
                {opportunity.researchAngles.map((angle) => (
                  <div key={angle} className="rounded-2xl border border-white/10 bg-white/[0.035] p-4 text-sm leading-6 text-slate-300">
                    <CheckCircle2 className="mb-3 size-5 text-emerald-300" />
                    {angle}
                  </div>
                ))}
              </div>
            </DossierSection>

            <DossierSection title="Goal Preview" icon={Target} eyebrow="Measurable first goals">
              <div className="space-y-3">
                {opportunity.brief.goal_previews.map((goal) => (
                  <div key={goal.id} className="rounded-2xl border border-emerald-300/20 bg-emerald-300/[0.06] p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold text-emerald-50">{goal.title}</h3>
                        <p className="mt-2 text-sm leading-6 text-slate-400">
                          {goal.metric_name ?? "metric"} on {goal.dataset ?? "scoped dataset"} vs {goal.baseline ?? "baseline"}
                        </p>
                      </div>
                      <div className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1 font-mono text-xs text-emerald-100">
                        {Math.round(goal.goalability * 100)}% goal-ready
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 text-xs text-slate-400 sm:grid-cols-3">
                      <span>compute: {goal.compute_need}</span>
                      <span>window: {goal.time_window_days ?? "n/a"} days</span>
                      <span>risk: {Math.round(goal.risk * 100)}%</span>
                    </div>
                    <ul className="mt-3 space-y-1 text-sm leading-6 text-slate-300">
                      {goal.first_steps.map((step) => (
                        <li key={step} className="flex gap-2">
                          <span className="mt-2 size-1.5 shrink-0 rounded-full bg-emerald-200" />
                          <span>{step}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </DossierSection>

            <DossierSection title="30 天推进计划" icon={Route} eyebrow="Execution path">
              <div className="space-y-3">
                {opportunity.thirtyDayPlan.map((item, index) => (
                  <div key={item.week} className="grid gap-3 rounded-2xl border border-white/10 bg-white/[0.035] p-4 md:grid-cols-[120px_1fr]">
                    <div>
                      <div className="flex size-9 items-center justify-center rounded-2xl bg-white/[0.06] font-mono text-sm font-semibold text-cyan-100">{index + 1}</div>
                      <div className="mt-2 font-mono text-xs text-slate-500">{item.week}</div>
                    </div>
                    <div>
                      <div className="font-semibold text-white">{item.goal}</div>
                      <div className="mt-1 text-sm leading-6 text-slate-400">产出：{item.output}</div>
                    </div>
                  </div>
                ))}
              </div>
            </DossierSection>
          </div>

          <aside className="space-y-5 lg:sticky lg:top-24">
            <div className="rounded-[28px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/25 backdrop-blur-xl">
              <div className="flex items-center gap-2 text-lg font-semibold text-white">
                <Database className="size-5 text-cyan-200" />
                RH 交接包
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-400">
                Discovery 到此结束判断；下一步交给 RH 做论文入库、baseline、gap、证据门控和实验前方案收敛。
              </p>
              <div className="mt-4">
                <DiscoveryHandoffButton
                  slug={opportunity.slug}
                  selectedGoalPreviewIds={selectedGoalPreviewIds}
                />
              </div>
              <div className="mt-5 space-y-2">
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">初始检索词</div>
                {opportunity.brief.rh_handoff.initial_queries.map((query) => (
                  <div key={query} className="rounded-xl border border-white/10 bg-black/20 p-3 font-mono text-xs leading-5 text-slate-300">{query}</div>
                ))}
              </div>
            </div>

            <div className="rounded-[28px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/25 backdrop-blur-xl">
              <div className="flex items-center gap-2 text-lg font-semibold text-white">
                <FileText className="size-5 text-violet-200" />
                种子论文 / 来源
              </div>
              <div className="mt-4 space-y-3">
                {opportunity.brief.seed_papers.length === 0 ? (
                  <p className="rounded-2xl border border-white/10 bg-white/[0.035] p-4 text-sm leading-6 text-slate-500">
                    这一方向先从实时信号和检索词开始，不强行伪造种子论文。
                  </p>
                ) : (
                  opportunity.brief.seed_papers.map((paper) => (
                    <a key={paper.title} href={paper.url ?? "#"} target="_blank" rel="noreferrer" className="block rounded-2xl border border-white/10 bg-white/[0.035] p-3 text-sm transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.04]">
                      <div className="flex items-start justify-between gap-3">
                        <span className="font-medium leading-5 text-white">{paper.title}</span>
                        <ExternalLink className="size-4 shrink-0 text-slate-600" />
                      </div>
                      <div className="mt-2 font-mono text-xs text-slate-500">{paper.arxiv_id ?? paper.doi ?? paper.year}</div>
                    </a>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-[28px] border border-amber-300/20 bg-amber-300/10 p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-amber-100">
                <BarChart3 className="size-4" />
                展示时应强调
              </div>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-amber-50/75">
                {opportunity.brief.risks.map((risk) => (
                  <li key={risk} className="flex gap-2">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-amber-200" />
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}

function Pill({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "emerald" | "cyan" | "muted" }) {
  const toneClass = {
    default: "border-white/10 bg-white/[0.05] text-slate-200",
    emerald: "border-emerald-300/25 bg-emerald-300/10 text-emerald-100",
    cyan: "border-cyan-300/25 bg-cyan-300/10 text-cyan-100",
    muted: "border-white/10 bg-white/[0.03] text-slate-400",
  }[tone];

  return <span className={cn("rounded-full border px-3 py-1 text-xs font-medium", toneClass)}>{children}</span>;
}

function DossierSection({
  children,
  eyebrow,
  icon: Icon,
  title,
}: {
  children: React.ReactNode;
  eyebrow: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
}) {
  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-950/72 p-5 shadow-xl shadow-black/25 backdrop-blur-xl">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-2xl bg-white/[0.06] text-cyan-100">
          <Icon className="size-5" />
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">{eyebrow}</div>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-white">{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}

function ScoreCard({ description, label, value }: { description: string; label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold tabular-nums text-white">{value}</div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-gradient-to-r from-cyan-300 to-violet-300" style={{ width: `${value}%` }} />
      </div>
      <div className="mt-2 text-[11px] leading-4 text-slate-500">{description}</div>
    </div>
  );
}

function sourceKindLabel(kind: string): string {
  const labels: Record<string, string> = {
    paper: "论文",
    product: "产品",
    benchmark: "评测",
    repo: "开源",
    workshop: "会议",
    blog: "博客",
  };
  return labels[kind] ?? kind;
}
