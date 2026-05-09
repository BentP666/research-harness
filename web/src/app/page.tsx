"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  FlaskConical,
  PenLine,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Zap,
} from "lucide-react";
import { fetchDashboardStats, fetchTopics } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n-provider";
import type { DashboardStats, Topic } from "@/lib/types";
import type { ComponentType } from "react";

interface ProductAction {
  title: string;
  body: string;
  href: string;
  cta: string;
  icon: ComponentType<{ className?: string }>;
}

function Metric({ label, value, loading }: { label: string; value?: number; loading: boolean }) {
  return (
    <div className="rounded-2xl border bg-white/70 px-4 py-3 shadow-sm backdrop-blur dark:bg-slate-900/60">
      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      {loading ? (
        <Skeleton className="mt-2 h-7 w-14" />
      ) : (
        <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-950 dark:text-white">
          {(value ?? 0).toLocaleString()}
        </p>
      )}
    </div>
  );
}

function ResearchPreview() {
  const { t } = useT();
  const stages = [
    t("dashboard.workbench.preview.stage1"),
    t("dashboard.workbench.preview.stage2"),
    t("dashboard.workbench.preview.stage3"),
  ];

  return (
    <Card className="overflow-hidden rounded-[1.75rem] border-slate-200/80 bg-slate-950 text-white shadow-2xl shadow-indigo-950/20 dark:border-slate-800">
      <CardContent className="p-0">
        <div className="border-b border-white/10 bg-white/[0.03] px-5 py-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
                {t("dashboard.workbench.preview.kicker")}
              </p>
              <h2 className="mt-2 text-lg font-semibold tracking-tight">
                {t("dashboard.workbench.preview.title")}
              </h2>
            </div>
            <Badge className="bg-emerald-400/10 text-emerald-200 ring-1 ring-emerald-400/20">
              <span className="size-1.5 rounded-full bg-emerald-300" />
              {t("dashboard.workbench.preview.status")}
            </Badge>
          </div>
        </div>

        <div className="grid gap-4 p-5">
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-2xl bg-white/[0.06] p-3 ring-1 ring-white/10">
              <p className="text-[11px] text-slate-400">{t("dashboard.workbench.preview.papers")}</p>
              <p className="mt-1 text-2xl font-semibold">42</p>
            </div>
            <div className="rounded-2xl bg-white/[0.06] p-3 ring-1 ring-white/10">
              <p className="text-[11px] text-slate-400">{t("dashboard.workbench.preview.evidence")}</p>
              <p className="mt-1 text-2xl font-semibold">128</p>
            </div>
            <div className="rounded-2xl bg-white/[0.06] p-3 ring-1 ring-white/10">
              <p className="text-[11px] text-slate-400">{t("dashboard.workbench.preview.gaps")}</p>
              <p className="mt-1 text-2xl font-semibold">7</p>
            </div>
          </div>

          <div className="rounded-2xl bg-white/[0.06] p-4 ring-1 ring-white/10">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-medium">{t("dashboard.workbench.preview.pipeline")}</p>
              <p className="text-xs text-indigo-200">72%</p>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/10">
              <div className="h-full w-[72%] rounded-full bg-gradient-to-r from-indigo-400 to-cyan-300" />
            </div>
            <div className="mt-4 space-y-3">
              {stages.map((stage, index) => (
                <div key={stage} className="flex items-center gap-3 text-sm">
                  <CheckCircle2 className="size-4 text-emerald-300" />
                  <span className={index === stages.length - 1 ? "text-white" : "text-slate-300"}>
                    {stage}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-indigo-300/20 bg-indigo-400/10 p-4">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-indigo-200">
              {t("dashboard.workbench.preview.nextLabel")}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-slate-100">
              {t("dashboard.workbench.preview.nextAction")}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ActionCard({ action }: { action: ProductAction }) {
  const Icon = action.icon;
  return (
    <Link
      href={action.href}
      className="group rounded-3xl border bg-white/75 p-5 shadow-sm transition duration-200 hover:-translate-y-1 hover:border-indigo-200 hover:shadow-xl hover:shadow-indigo-950/[0.06] dark:bg-slate-900/65 dark:hover:border-indigo-800"
    >
      <div className="mb-5 flex size-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-900 ring-1 ring-slate-200 transition group-hover:bg-indigo-600 group-hover:text-white group-hover:ring-indigo-500 dark:bg-slate-800 dark:text-white dark:ring-slate-700">
        <Icon className="size-5" />
      </div>
      <h3 className="text-lg font-semibold tracking-tight text-slate-950 dark:text-white">
        {action.title}
      </h3>
      <p className="mt-2 min-h-14 text-sm leading-6 text-muted-foreground">
        {action.body}
      </p>
      <span className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-indigo-600 transition group-hover:gap-2 dark:text-indigo-300">
        {action.cta}
        <ArrowRight className="size-4" />
      </span>
    </Link>
  );
}

function RecentTopics({ topics, loading }: { topics: Topic[]; loading: boolean }) {
  const { t } = useT();

  if (loading) {
    return (
      <Card className="rounded-3xl bg-white/70 dark:bg-slate-900/60">
        <CardContent className="space-y-4 p-6">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-16 w-full rounded-2xl" />
        </CardContent>
      </Card>
    );
  }

  if (!topics.length) {
    return (
      <Card className="rounded-3xl border-indigo-100 bg-gradient-to-br from-white to-indigo-50/60 shadow-sm dark:border-indigo-950 dark:from-slate-900 dark:to-indigo-950/30">
        <CardContent className="grid gap-6 p-6 sm:p-7 lg:grid-cols-[1fr_0.9fr] lg:items-center">
          <div>
            <Badge variant="outline" className="mb-4 bg-white/70 dark:bg-slate-900/70">
              <Sparkles className="size-3" />
              {t("dashboard.workbench.empty.badge")}
            </Badge>
            <h2 className="text-2xl font-semibold tracking-tight text-slate-950 dark:text-white">
              {t("dashboard.workbench.empty.title")}
            </h2>
            <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
              {t("dashboard.workbench.empty.body")}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button render={<Link href="/topics/new" />}>
                {t("dashboard.cta.createTopic")}
              </Button>
              <Button variant="outline" render={<Link href="/demo" />}>
                {t("dashboard.workbench.demoCta")}
              </Button>
            </div>
          </div>
          <div className="rounded-2xl border bg-white/80 p-4 shadow-sm dark:bg-slate-950/60">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              {t("dashboard.workbench.handoff.label")}
            </p>
            <p className="mt-3 rounded-xl bg-slate-950 p-4 font-mono text-xs leading-6 text-slate-100 dark:bg-black">
              {t("dashboard.workbench.handoff.prompt")}
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="rounded-3xl bg-white/70 dark:bg-slate-900/60">
      <CardContent className="p-6 sm:p-7">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-medium text-indigo-600 dark:text-indigo-300">
              {t("dashboard.workbench.recent.kicker")}
            </p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight">
              {t("dashboard.workbench.recent.title")}
            </h2>
          </div>
          <Button variant="outline" size="sm" render={<Link href="/research" />}>
            {t("dashboard.workbench.viewWorkflow")}
          </Button>
        </div>

        <div className="mt-6 grid gap-3 lg:grid-cols-2">
          {topics.slice(0, 4).map((topic) => (
            <Link
              key={topic.id}
              href={`/topics/${topic.id}`}
              className="group rounded-2xl border bg-background/80 p-4 transition hover:border-indigo-200 hover:bg-indigo-50/40 dark:hover:border-indigo-800 dark:hover:bg-indigo-950/20"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h3 className="truncate font-semibold text-slate-950 dark:text-white">
                    {topic.name}
                  </h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {topic.current_stage ?? t("dashboard.stageNotStarted")} · {t("dashboard.papersCount", { count: topic.paper_count })}
                  </p>
                </div>
                <ArrowRight className="size-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-indigo-500" />
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { t } = useT();
  const statsQuery = useQuery({ queryKey: ["dashboard-stats"], queryFn: fetchDashboardStats });
  const topicsQuery = useQuery({ queryKey: ["topics"], queryFn: () => fetchTopics() });
  const stats: DashboardStats | undefined = statsQuery.data;
  const topics = topicsQuery.data ?? [];

  const actions: ProductAction[] = [
    {
      title: t("dashboard.workbench.actions.search.title"),
      body: t("dashboard.workbench.actions.search.body"),
      href: "/topics/new",
      cta: t("dashboard.workbench.actions.search.cta"),
      icon: Search,
    },
    {
      title: t("dashboard.workbench.actions.read.title"),
      body: t("dashboard.workbench.actions.read.body"),
      href: "/library",
      cta: t("dashboard.workbench.actions.read.cta"),
      icon: BookOpen,
    },
    {
      title: t("dashboard.workbench.actions.gap.title"),
      body: t("dashboard.workbench.actions.gap.body"),
      href: "/research",
      cta: t("dashboard.workbench.actions.gap.cta"),
      icon: Target,
    },
    {
      title: t("dashboard.workbench.actions.write.title"),
      body: t("dashboard.workbench.actions.write.body"),
      href: "/reports",
      cta: t("dashboard.workbench.actions.write.cta"),
      icon: PenLine,
    },
  ];

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-10 p-4 sm:p-6 lg:p-8">
      <section className="grid gap-8 lg:grid-cols-[1.02fr_0.98fr] lg:items-center">
        <div className="relative overflow-hidden rounded-[2rem] border bg-white/80 p-7 shadow-sm backdrop-blur sm:p-10 dark:bg-slate-900/65">
          <div className="pointer-events-none absolute -right-28 -top-28 size-80 rounded-full bg-indigo-300/20 blur-3xl dark:bg-indigo-600/10" />
          <div className="relative">
            <Badge variant="outline" className="mb-5 bg-background/80 px-3 py-1">
              <Zap className="size-3 text-indigo-500" />
              {t("dashboard.workbench.eyebrow")}
            </Badge>
            <h1 className="max-w-3xl text-4xl font-semibold tracking-[-0.035em] text-slate-950 sm:text-6xl dark:text-white">
              {t("dashboard.workbench.title")}
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-8 text-muted-foreground sm:text-lg">
              {t("dashboard.workbench.subtitle")}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" render={<Link href="/topics/new" />}>
                {t("dashboard.cta.createTopic")}
                <ArrowRight className="size-4" />
              </Button>
              <Button size="lg" variant="outline" render={<Link href="/demo" />}>
                {t("dashboard.workbench.demoCta")}
              </Button>
            </div>
            <div className="mt-8 grid max-w-2xl grid-cols-3 gap-3">
              <Metric label={t("dashboard.statTopics")} value={stats?.total_topics} loading={statsQuery.isPending} />
              <Metric label={t("dashboard.statPapers")} value={stats?.total_papers} loading={statsQuery.isPending} />
              <Metric label={t("dashboard.statArtifacts")} value={stats?.total_artifacts} loading={statsQuery.isPending} />
            </div>
          </div>
        </div>

        <ResearchPreview />
      </section>

      <section>
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-medium text-indigo-600 dark:text-indigo-300">
              {t("dashboard.workbench.questionKicker")}
            </p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950 dark:text-white">
              {t("dashboard.workbench.question")}
            </h2>
          </div>
          <p className="max-w-md text-sm text-muted-foreground">
            {t("dashboard.workbench.questionHint")}
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {actions.map((action) => (
            <ActionCard key={action.title} action={action} />
          ))}
        </div>
      </section>

      <RecentTopics topics={topics} loading={topicsQuery.isPending} />

      <section className="grid gap-4 lg:grid-cols-[1.35fr_0.65fr]">
        <Card className="rounded-3xl bg-white/70 dark:bg-slate-900/60">
          <CardContent className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center sm:justify-between sm:p-7">
            <div className="flex items-start gap-4">
              <div className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-200 dark:ring-emerald-900/60">
                <ShieldCheck className="size-5" />
              </div>
              <div>
                <h2 className="text-lg font-semibold tracking-tight">
                  {t("dashboard.workbench.agentFirst.title")}
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                  {t("dashboard.workbench.agentFirst.body")}
                </p>
              </div>
            </div>
            <Button variant="outline" render={<Link href="/research" />}>
              <FlaskConical className="size-4" />
              {t("dashboard.workbench.viewWorkflow")}
            </Button>
          </CardContent>
        </Card>

        <Card className="rounded-3xl border-dashed bg-white/50 dark:bg-slate-900/40">
          <CardContent className="p-6 sm:p-7">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <TrendingUp className="size-4" />
              {t("dashboard.workbench.labs.eyebrow")}
            </div>
            <h2 className="text-lg font-semibold tracking-tight">
              {t("dashboard.workbench.labs.title")}
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {t("dashboard.workbench.labs.body")}
            </p>
            <Button className="mt-5" size="sm" variant="outline" render={<Link href="/research/trends" />}>
              {t("nav.trends")}
            </Button>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
