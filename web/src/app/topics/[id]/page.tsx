"use client";

import { useParams } from "next/navigation";
import {
  useQueries,
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import {
  ArrowLeft,
  Calendar,
  MapPin,
  AlertTriangle,
  Clock,
  FileText,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  MinusCircle,
  BarChart3,
} from "lucide-react";
import Link from "next/link";
import {
  fetchTopicDetail,
  fetchTopicArtifacts,
  fetchTopicEvents,
  fetchTopicDecisions,
  fetchTopicIssues,
  fetchTopicAutonomy,
  updateTopicAutonomy,
  fetchTopicTier,
  updateTopicTier,
  fetchRollbackLog,
  fetchRubricScores,
  fetchStageSummary,
  fetchStagePolicy,
  type RubricScore,
} from "@/lib/api";
import {
  RESEARCH_STAGES,
  STAGE_LABELS,
  STAGE_BG_COLORS,
  STAGE_TEXT_COLORS,
  type ResearchStage,
  type StageEvent,
  type ReviewIssue,
  type TopicDetail,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { NextActionsCard } from "@/components/topic/next-actions-card";
import { useT } from "@/lib/i18n-provider";
import { PaperSearchPanel } from "@/components/topic/paper-search-panel";
import { ExportMenu } from "@/components/brand/export-menu";
import { topicBibtexUrl, fetchTopicBibtex } from "@/lib/api";
import { AnalysisPanel } from "@/components/topic/analysis-panel";
import FieldBriefCard from "@/components/topic/field-brief-card";
import GoalPoolCard from "@/components/topic/goal-pool-card";
import MethodAtomsLibrary from "@/components/topic/method-atoms-library";
import ExperimentMatrixCard from "@/components/topic/experiment-matrix-card";
import { VenueDecisionBanner, VenueStyleKitCard } from "@/components/topic/venue-kit";
import { WritePanel } from "@/components/topic/write-panel";
import { TopicCostCard } from "@/components/topic/topic-cost-card";
import { ClaimVerificationPanel } from "@/components/topic/claim-verification-panel";
import { NextStageHero } from "@/components/topic/next-stage-hero";
import {
  StageGraph,
  type StageGraphSummary,
} from "@/components/topic/stage-graph";
import { StageDrawer } from "@/components/topic/stage-drawer";
import { ExperimentLeaderboardCard } from "@/components/topic/experiment-leaderboard-card";
import { ExpansionPanel } from "@/components/topic/expansion-panel";
import { WorkflowPipeline } from "@/components/topic/workflow-pipeline";
import { RetrievalLogTimeline } from "@/components/topic/retrieval-log-timeline";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(dateStr: string | null | undefined): string {
  if (!dateStr) return "--";
  const d = new Date(dateStr);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// Severity badge
// ---------------------------------------------------------------------------

function SeverityBadge({ severity }: { severity: ReviewIssue["severity"] }) {
  const styles: Record<string, string> = {
    critical: "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300",
    high: "bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300",
    medium: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/50 dark:text-yellow-300",
    low: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  };

  return (
    <Badge className={cn("text-xs font-medium", styles[severity] ?? styles.low)}>
      {severity}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Issue status icon
// ---------------------------------------------------------------------------

function IssueStatusIcon({ status }: { status: ReviewIssue["status"] }) {
  switch (status) {
    case "resolved":
      return <CheckCircle2 className="size-4 text-emerald-500" />;
    case "wontfix":
      return <MinusCircle className="size-4 text-slate-400" />;
    case "in_progress":
      return <Clock className="size-4 text-blue-500" />;
    default:
      return <XCircle className="size-4 text-red-400" />;
  }
}

// ---------------------------------------------------------------------------
// Event type badge
// ---------------------------------------------------------------------------

function EventTypeBadge({ type }: { type: StageEvent["event_type"] }) {
  const styles: Record<string, string> = {
    advance: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300",
    gate_check: "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300",
    artifact_record: "bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300",
    decision: "bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300",
  };

  return (
    <Badge className={cn("text-xs font-medium", styles[type] ?? "bg-slate-100 text-slate-600")}>
      {type.replace(/_/g, " ")}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Header skeleton
// ---------------------------------------------------------------------------

function HeaderSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-5 w-24" />
      <Skeleton className="h-7 w-64" />
      <div className="flex gap-2">
        <Skeleton className="h-5 w-20 rounded-full" />
        <Skeleton className="h-5 w-20 rounded-full" />
        <Skeleton className="h-5 w-32 rounded-full" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Autonomy + Tier controls
// ---------------------------------------------------------------------------

const AUTONOMY_LEVELS = [
  { value: "L0", label: "Step-by-step", desc: "Pause after every action" },
  { value: "L1", label: "Stage-by-stage", desc: "Pause at every stage boundary" },
  { value: "L2", label: "Smart checkpoints", desc: "Pause only at the big ones (recommended)" },
  { value: "L3", label: "Full auto", desc: "Let it run end-to-end" },
] as const;

const TIER_OPTIONS = [
  { value: "economy", label: "Economy", cost: "$3-8/topic" },
  { value: "standard", label: "Standard", cost: "$15-30/topic" },
  { value: "premium", label: "Premium", cost: "$60-150/topic" },
] as const;

function AutonomyPanel({ topicId }: { topicId: number }) {
  const qc = useQueryClient();
  const autonomyQ = useQuery({
    queryKey: ["topic-autonomy", topicId],
    queryFn: () => fetchTopicAutonomy(topicId),
  });
  const autonomyMut = useMutation({
    mutationFn: (level: string) => updateTopicAutonomy(topicId, level),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["topic-autonomy", topicId] }),
  });

  const currentLevel = autonomyQ.data?.level ?? "L2";

  return (
    <Card>
      <CardContent className="flex flex-col gap-2 pt-6 sm:flex-row sm:items-center sm:gap-6">
        <p className="text-xs font-medium text-muted-foreground w-32 shrink-0">
          How hands-on?
        </p>
        <div className="flex flex-wrap gap-1.5">
          {AUTONOMY_LEVELS.map((al) => (
            <button
              key={al.value}
              type="button"
              onClick={() => autonomyMut.mutate(al.value)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                currentLevel === al.value
                  ? "bg-blue-600 text-white"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              )}
              title={al.desc}
            >
              {al.label}
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Rubric scorecard
// ---------------------------------------------------------------------------

function ScoringCard({ topicId }: { topicId: number }) {
  const qc = useQueryClient();

  const tierQ = useQuery({
    queryKey: ["topic-tier", topicId],
    queryFn: () => fetchTopicTier(topicId),
  });
  const scoresQ = useQuery({
    queryKey: ["rubric-scores", topicId],
    queryFn: () => fetchRubricScores(topicId),
  });
  const rollbackQ = useQuery({
    queryKey: ["topic-rollback-log", topicId],
    queryFn: () => fetchRollbackLog(topicId),
  });

  const tierMut = useMutation({
    mutationFn: (tier: string) => updateTopicTier(topicId, tier),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topic-tier", topicId] }),
  });

  const currentTier = tierQ.data?.quality_tier ?? "standard";
  const tierConfig = tierQ.data?.config;
  const scores = scoresQ.data ?? [];
  const rollbacks = rollbackQ.data ?? [];

  const latest = scores.length > 0 ? scores[0] : null;
  const isShadow = !!latest?.shadow_verdict;

  // Build a per-stage summary of the latest score for each stage + whether
  // that stage has been rolled back at any point.
  const byStage = new Map<string, RubricScore>();
  for (const s of scores) {
    if (!byStage.has(s.stage)) byStage.set(s.stage, s);
  }
  const rolledBackStages = new Set(rollbacks.map((r) => r.from_stage));

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="size-4" />
            <CardTitle className="text-sm">Quality scorecard</CardTitle>
            {isShadow && (
              <Badge
                variant="outline"
                className="text-[10px] h-4 px-1.5 text-amber-600 border-amber-300"
                title="Shadow mode — verdicts are logged but won't trigger rollback"
              >
                shadow
              </Badge>
            )}
            {latest && (
              <Link
                href="/settings/scoring"
                className="text-[11px] text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
              >
                Strictness rules →
              </Link>
            )}
          </div>

          {/* Tier chip group — moved from TopicControlsPanel per Phase E */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium text-muted-foreground">
              Strictness
            </span>
            <div className="flex gap-1">
              {TIER_OPTIONS.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => tierMut.mutate(t.value)}
                  className={cn(
                    "rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors",
                    currentTier === t.value
                      ? "bg-blue-600 text-white"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  )}
                  title={t.cost}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        {tierConfig && (
          <p className="text-xs text-muted-foreground">
            {tierConfig.judge_mode} judge, {tierConfig.retries} retries,{" "}
            {tierConfig.rubric_dimensions} rubric dims, est.{" "}
            {tierConfig.cost_estimate}
          </p>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Last-scored summary banner */}
        <LastScoredBanner
          latest={latest}
          rollbacks={rollbacks}
          scoreCount={scores.length}
        />

        {scores.length > 0 && (
          <div className="space-y-4">
            {Array.from(byStage.entries()).map(([stage, s]) => (
              <StageScoreRow
                key={stage}
                stage={stage}
                score={s}
                wasRolledBack={rolledBackStages.has(stage)}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function LastScoredBanner({
  latest,
  rollbacks,
  scoreCount,
}: {
  latest: RubricScore | null;
  rollbacks: Array<{ from_stage: string; to_stage: string; created_at: string }>;
  scoreCount: number;
}) {
  if (!latest) {
    return (
      <p className="text-xs text-muted-foreground">
        No scored artifacts yet. Runs a rubric score when each stage completes.
      </p>
    );
  }

  const lastRollback =
    rollbacks.length > 0
      ? rollbacks.reduce(
          (acc, r) =>
            new Date(r.created_at) > new Date(acc.created_at) ? r : acc,
          rollbacks[0]
        )
      : null;

  const verdict = latest.shadow_verdict ?? latest.verdict;
  const verdictTone =
    verdict === "pass"
      ? "text-emerald-700 dark:text-emerald-400"
      : verdict === "rollback"
        ? "text-red-700 dark:text-red-400"
        : "text-amber-700 dark:text-amber-400";
  const scoredAt = formatTimestamp(latest.scored_at);

  return (
    <div className="rounded-md border bg-muted/30 p-3 text-xs">
      <p>
        <span className="text-muted-foreground">Last scored: </span>
        <span className="font-medium capitalize">{latest.stage}</span>
        <span className="text-muted-foreground"> on {scoredAt}</span>
        <span className="text-muted-foreground"> → </span>
        <span className={cn("font-mono tabular-nums", verdictTone)}>
          {latest.weighted_total.toFixed(1)} ({verdict})
        </span>
        {latest.shadow_verdict && (
          <span className="text-muted-foreground">
            {" "}
            · live mode would have {latest.shadow_verdict}ed
          </span>
        )}
      </p>
      {lastRollback && (
        <p className="mt-1 text-muted-foreground">
          Last rollback:{" "}
          <span className="font-medium capitalize">
            {lastRollback.from_stage}
          </span>{" "}
          → <span className="capitalize">{lastRollback.to_stage}</span>
          {" on "}
          {formatTimestamp(lastRollback.created_at)}
          {" ("}
          {rollbacks.length} total
          {")"}
        </p>
      )}
      {scoreCount > 1 && (
        <p className="mt-1 text-[11px] text-muted-foreground">
          {scoreCount} scored artifacts on record — latest first below.
        </p>
      )}
    </div>
  );
}

function StageScoreRow({
  stage,
  score,
  wasRolledBack,
}: {
  stage: string;
  score: RubricScore;
  wasRolledBack: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium capitalize">{stage}</span>
          {wasRolledBack && (
            <Badge
              variant="outline"
              className="text-[10px] h-4 px-1.5 text-red-600 border-red-300"
              title="This stage has been rolled back at least once"
            >
              rolled back
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs tabular-nums font-mono">
            {score.weighted_total.toFixed(1)}
          </span>
          <Badge
            variant={score.verdict === "pass" ? "secondary" : "destructive"}
            className="text-[10px] h-4 px-1.5"
          >
            {score.verdict}
          </Badge>
          {score.shadow_verdict && (
            <Badge
              variant="outline"
              className="text-[10px] h-4 px-1.5 text-amber-600 border-amber-300"
            >
              would: {score.shadow_verdict}
            </Badge>
          )}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-1">
        {Object.entries(score.dimension_scores).map(([dim, val]) => (
          <div
            key={dim}
            className="flex items-center justify-between text-xs text-muted-foreground"
          >
            <span className="truncate">{dim.replace(/_/g, " ")}</span>
            <span className="tabular-nums font-mono ml-1">
              {(val as number).toFixed(1)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function TopicDetailPage() {
  const { t } = useT();
  const params = useParams();
  const topicId = Number(params.id);
  const queryClient = useQueryClient();
  const [drawerStage, setDrawerStage] = useState<ResearchStage | null>(null);

  // Queries
  const topicQ = useQuery({
    queryKey: ["topic", topicId],
    queryFn: () => fetchTopicDetail(topicId),
    enabled: !isNaN(topicId),
  });

  const eventsQ = useQuery({
    queryKey: ["topic-events", topicId],
    queryFn: () => fetchTopicEvents(topicId),
    enabled: !isNaN(topicId),
  });

  const decisionsQ = useQuery({
    queryKey: ["topic-decisions", topicId],
    queryFn: () => fetchTopicDecisions(topicId),
    enabled: !isNaN(topicId),
  });

  const rollbackLogQ = useQuery({
    queryKey: ["topic-rollback-log-page", topicId],
    queryFn: () => fetchRollbackLog(topicId),
    enabled: !isNaN(topicId),
  });

  const issuesQ = useQuery({
    queryKey: ["topic-issues", topicId],
    queryFn: () => fetchTopicIssues(topicId),
    enabled: !isNaN(topicId),
  });

  // Per-stage audit summaries — feed the StageGraph node chips (ran/planned +
  // invariant count). Each query is cheap + independently cached.
  const summaryResults = useQueries({
    queries: RESEARCH_STAGES.map((stage) => ({
      queryKey: ["stage-summary", topicId, stage],
      queryFn: () => fetchStageSummary(topicId, stage),
      enabled: !isNaN(topicId),
      staleTime: 30_000,
    })),
  });
  const policyResults = useQueries({
    queries: RESEARCH_STAGES.map((stage) => ({
      queryKey: ["stage-policy", topicId, stage],
      queryFn: () => fetchStagePolicy(topicId, stage),
      enabled: !isNaN(topicId),
      staleTime: 60_000,
    })),
  });
  const stageSummaries = useMemo(() => {
    const out: Partial<Record<ResearchStage, StageGraphSummary>> = {};
    RESEARCH_STAGES.forEach((stage, i) => {
      const s = summaryResults[i]?.data;
      const p = policyResults[i]?.data;
      if (!s) return;
      // Red dot semantically means "blocked" (per legend). Only count
      // critical/high invariants here — medium-severity advisories are
      // surfaced in the drawer's issue list, not as a stop signal.
      const blockingCount = (p?.invariant_violations ?? []).filter(
        (v) => v.severity === "critical" || v.severity === "high",
      ).length;
      out[stage] = {
        ran: s.primitives_ran,
        planned: s.primitives_planned,
        invariantViolations: blockingCount,
        evidenceCount: s.evidence_count ?? 0,
      };
    });
    return out;
  }, [summaryResults, policyResults]);

  const topic: TopicDetail | undefined = topicQ.data;
  const events = eventsQ.data?.events ?? [];
  const issues = issuesQ.data?.issues ?? [];

  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
    queryClient.invalidateQueries({ queryKey: ["topic-events", topicId] });
    queryClient.invalidateQueries({ queryKey: ["topic-issues", topicId] });
    queryClient.invalidateQueries({ queryKey: ["stage-summary", topicId] });
    queryClient.invalidateQueries({ queryKey: ["stage-policy", topicId] });
  }, [queryClient, topicId]);

  return (
    <div className="space-y-6 p-4 pb-20 sm:p-6 lg:p-8 lg:pb-20">
      {/* ---------------------------------------------------------------- */}
      {/* Back link + Header                                               */}
      {/* ---------------------------------------------------------------- */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Link
            href="/topics"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-3.5" />
            {t("topicPage.backLink")}
          </Link>
          <div className="flex items-center gap-2">
            <ExportMenu
              label="Export"
              targets={[
                {
                  label: "Paper pool as BibTeX",
                  icon: "bibtex",
                  href: topicBibtexUrl(topicId),
                  hint: "Import to Zotero / BibLaTeX",
                },
                {
                  label: "Copy BibTeX to clipboard",
                  icon: "copy",
                  onAction: async () => {
                    const text = await fetchTopicBibtex(topicId);
                    await navigator.clipboard.writeText(text);
                  },
                },
              ]}
            />
            <Link
              href={`/topics/${topicId}/reports`}
              className="inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1 text-xs font-medium hover:bg-muted"
            >
              <FileText className="size-3.5" />
              Advisor reports
            </Link>
          </div>
        </div>

        {topicQ.isPending ? (
          <HeaderSkeleton />
        ) : topic ? (
          <div className="space-y-3">
            {/* Title row */}
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">
                {topic.name}
              </h1>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {topic.domain_name ?? "No domain"}
                {topic.description ? ` -- ${topic.description}` : ""}
              </p>
            </div>

            {/* Metadata badges */}
            <div className="flex flex-wrap items-center gap-2">
              {topic.target_venue && (
                <Badge variant="outline" className="text-xs gap-1">
                  <MapPin className="size-3" />
                  {topic.target_venue}
                </Badge>
              )}
              {topic.deadline && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Calendar className="size-3" />
                  {topic.deadline}
                </Badge>
              )}
              {topic.current_stage && (
                <Badge
                  variant="secondary"
                  className={cn(
                    "text-xs font-medium",
                    STAGE_BG_COLORS[topic.current_stage],
                    STAGE_TEXT_COLORS[topic.current_stage]
                  )}
                >
                  {STAGE_LABELS[topic.current_stage]}
                  {topic.stage_status ? ` / ${topic.stage_status}` : ""}
                </Badge>
              )}
              {topic.gate_status && (
                <GateStatusBadge status={topic.gate_status} />
              )}
              {(topic.blocking_issue_count ?? 0) > 0 && (
                <Badge className="bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300 text-xs gap-1">
                  <AlertTriangle className="size-3" />
                  {topic.blocking_issue_count} blocking
                </Badge>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Topic not found.
          </p>
        )}
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Next stage hero CTA — primary action on this page                */}
      {/* ---------------------------------------------------------------- */}
      {topic && (
        <NextStageHero
          topicId={topicId}
          topicName={topic.name}
          currentStage={topic.current_stage}
          stageStatus={topic.stage_status}
          onRefresh={handleRefresh}
        />
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Workflow pipeline — merged stage graph + manual steps             */}
      {/* ---------------------------------------------------------------- */}
      {topic && (
        <WorkflowPipeline
          topicId={topicId}
          paperCount={topic.paper_count ?? 0}
          deepReadCount={0}
          currentStage={topic.current_stage as import("@/lib/types").ResearchStage | undefined}
          stageSummaries={stageSummaries}
          onStageClick={setDrawerStage}
        />
      )}

      <StageDrawer
        topicId={topicId}
        stage={drawerStage}
        open={drawerStage !== null}
        onOpenChange={(open) => {
          if (!open) setDrawerStage(null);
        }}
      />

      {/* ---------------------------------------------------------------- */}
      {/* Paper expansion — multi-round retrieval + deep-read with progress */}
      {/* ---------------------------------------------------------------- */}
      {topic && <ExpansionPanel topicId={topicId} />}

      {/* ---------------------------------------------------------------- */}
      {/* Experiment: method atoms + matrix + leaderboard */}
      {/* ---------------------------------------------------------------- */}
      {topic && topic.current_stage === "experiment" && (
        <>
          <div className="grid gap-4 md:grid-cols-5">
            <div className="md:col-span-2">
              <MethodAtomsLibrary topicId={topicId} />
            </div>
            <div className="md:col-span-3">
              <ExperimentMatrixCard topicId={topicId} />
            </div>
          </div>
        </>
      )}
      {topic && (
        <ExperimentLeaderboardCard topicId={topicId} />
      )}

      {/* ---------------------------------------------------------------- */}
      {/* What I'd work on next — stage-aware AI recommendations            */}
      {/* ---------------------------------------------------------------- */}
      {topic && (
        <NextActionsCard
          topicId={topicId}
          currentStage={topic.current_stage}
          paperCount={topic.paper_count ?? 0}
          hasDraft={false}
          hasReport={false}
        />
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Scoring — strictness (tier) + last verdict + rollback summary    */}
      {/* ---------------------------------------------------------------- */}
      {topic && <TopicCostCard topicId={topicId} />}

      {/* ---------------------------------------------------------------- */}
      {topic && <ScoringCard topicId={topicId} />}

      {/* ---------------------------------------------------------------- */}
      {/* Autonomy                                                         */}
      {/* ---------------------------------------------------------------- */}
      {topic && <AutonomyPanel topicId={topicId} />}

      {/* ---------------------------------------------------------------- */}
      {/* Stage-specific operation panels                                   */}
      {/* ---------------------------------------------------------------- */}
      {topic?.current_stage === "build" && (
        <PaperSearchPanel topicId={topicId} />
      )}
      {topic?.current_stage === "analyze" && (
        <>
          <FieldBriefCard topicId={topicId} />
          <GoalPoolCard topicId={topicId} />
          <AnalysisPanel topicId={topicId} />
          <ClaimVerificationPanel topicId={topicId} />
        </>
      )}
      {topic?.current_stage === "write" && (
        <>
          <VenueDecisionBanner topicId={topicId} />
          <VenueStyleKitCard topicId={topicId} />
          <WritePanel topicId={topicId} />
          <ClaimVerificationPanel topicId={topicId} />
        </>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Review issues + Activity sidebar — per-stage artifact lists moved */}
      {/* into the StageDrawer above.                                       */}
      {/* ---------------------------------------------------------------- */}
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Review Issues (left) */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold tracking-tight flex items-center gap-2">
            <ShieldAlert className="size-4" />
            {t("topicPage.reviewIssues")}
            {issues.length > 0 && (
              <span className="text-sm font-normal text-muted-foreground">
                ({issues.length})
              </span>
            )}
          </h2>

          {issuesQ.isPending ? (
            <Card>
              <CardContent>
                <div className="space-y-3">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              </CardContent>
            </Card>
          ) : issues.length === 0 ? (
            <Card>
              <CardContent>
                <p className="py-4 text-center text-sm text-muted-foreground">
                  No review issues recorded.
                </p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <div className="divide-y divide-foreground/5">
                  {issues.map((issue) => (
                    <div
                      key={issue.id}
                      className="flex items-start gap-3 px-4 py-3"
                    >
                      <IssueStatusIcon status={issue.status} />
                      <div className="flex-1 min-w-0 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <SeverityBadge severity={issue.severity} />
                          <span className="text-xs text-muted-foreground">
                            {issue.category}
                          </span>
                          {issue.blocking && (
                            <Badge variant="destructive" className="text-[10px] h-4 px-1.5">
                              blocking
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm">{issue.summary}</p>
                        {issue.recommended_action && (
                          <p className="text-xs text-muted-foreground">
                            Fix: {issue.recommended_action}
                          </p>
                        )}
                      </div>
                      <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                        {formatTimestamp(issue.created_at)}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Activity timeline (right sidebar) */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold tracking-tight flex items-center gap-2">
            <Clock className="size-4" />
            {t("topicPage.activity")}
          </h2>

          {eventsQ.isPending ? (
            <Card>
              <CardContent>
                <div className="space-y-3">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                </div>
              </CardContent>
            </Card>
          ) : events.length === 0 ? (
            <Card>
              <CardContent>
                <p className="py-4 text-center text-sm text-muted-foreground">
                  {t("topicPage.noEvents")}
                </p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <div className="divide-y divide-foreground/5 max-h-[600px] overflow-y-auto">
                  {events.map((event) => (
                    <div key={event.id} className="px-4 py-3 space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <EventTypeBadge type={event.event_type} />
                        {event.stage && (
                          <Badge
                            variant="secondary"
                            className={cn(
                              "text-[10px] h-4 px-1.5",
                              STAGE_BG_COLORS[event.stage],
                              STAGE_TEXT_COLORS[event.stage]
                            )}
                          >
                            {STAGE_LABELS[event.stage]}
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs text-muted-foreground">
                          {event.actor || "system"}
                        </span>
                        <span className="text-xs text-muted-foreground tabular-nums">
                          {formatTimestamp(event.created_at)}
                        </span>
                      </div>
                      {event.details &&
                        Object.keys(event.details).length > 0 && (
                          <p className="text-xs text-muted-foreground truncate">
                            {summarizeDetails(event.details)}
                          </p>
                        )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Retrieval log — interleaved with activity timeline */}
          <RetrievalLogTimeline topicId={topicId} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gate status badge (inline helper)
// ---------------------------------------------------------------------------

function GateStatusBadge({ status }: { status: string }) {
  const lower = status.toLowerCase();
  if (lower === "pass" || lower === "passed" || lower === "approved") {
    return (
      <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300 text-xs gap-1">
        <CheckCircle2 className="size-3" />
        Readiness: {status}
      </Badge>
    );
  }
  if (lower === "fail" || lower === "failed" || lower === "blocked") {
    return (
      <Badge className="bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300 text-xs gap-1">
        <XCircle className="size-3" />
        Readiness: {status}
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="text-xs">
      Gate: {status}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Summarize event details into one line
// ---------------------------------------------------------------------------

function summarizeDetails(details: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, val] of Object.entries(details)) {
    if (typeof val === "string") {
      parts.push(`${key}: ${val}`);
    } else if (typeof val === "number" || typeof val === "boolean") {
      parts.push(`${key}: ${String(val)}`);
    }
  }
  return parts.join(", ") || JSON.stringify(details).slice(0, 100);
}
