"use client";

/**
 * StageDrawer — right-side drilldown for a single stage.
 *
 * Collapses the legacy OrchestratorProgressCard / StageRoadmap / StagePanel
 * surfaces into one audit-grade view. Header strip carries the policy summary
 * (planned / ran / skipped / invariants / loopback state). Two tabs below:
 *
 *   • Trace     — chronological merge of primitive runs + events + skips +
 *                 rollbacks. Artifact-producing primitives are highlighted.
 *                 Background queries collapsed into a "+ N background calls"
 *                 expander.
 *   • Artifacts — the legacy stage-panel content, artifact by artifact, with
 *                 the latest rubric verdict inlined next to each item.
 *
 * Rollback lives in the sticky header — reason textarea + destructive button.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  RotateCcw,
  ShieldCheck,
  SkipForward,
  XCircle,
  Loader2,
} from "lucide-react";
import {
  fetchStagePrimitives,
  fetchStagePolicy,
  fetchStageSummary,
  fetchTopicArtifacts,
  fetchTopicDecisions,
  fetchTopicEvents,
  fetchRollbackLog,
  fetchRubricScores,
  rollbackTopic,
  type PrimitiveExecution,
  type RollbackLogEntry,
  type RubricScore,
} from "@/lib/api";
import {
  STAGE_LABELS,
  type Artifact,
  type DecisionLogEntry,
  type ResearchStage,
  type StageEvent,
} from "@/lib/types";
import { useT } from "@/lib/i18n-provider";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface StageDrawerProps {
  topicId: number;
  stage: ResearchStage | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type TraceRow =
  | { kind: "primitive"; at: string; data: PrimitiveExecution }
  | { kind: "event"; at: string; data: StageEvent }
  | { kind: "decision"; at: string; data: DecisionLogEntry }
  | { kind: "rollback"; at: string; data: RollbackLogEntry };

const ARTIFACT_PRODUCING_HINT = new Set([
  "paper_acquire",
  "paper_ingest",
  "claim_extract",
  "gap_detect",
  "direction_ranking",
  "section_draft",
  "outline_generate",
  "figure_generate",
  "experiment_run",
  "verified_registry_build",
  "adversarial_resolution",
  "algorithm_design_loop",
  "study_design",
  "expand_citations",
  "paper_search",
  "paper_finalize",
]);

export function StageDrawer({ topicId, stage, open, onOpenChange }: StageDrawerProps) {
  const { t } = useT();
  const stageKey = stage ?? "";
  const enabled = Boolean(open && stage);

  const primitivesQ = useQuery({
    queryKey: ["stage-primitives", topicId, stageKey],
    queryFn: () => fetchStagePrimitives(topicId, stageKey),
    enabled,
  });
  const policyQ = useQuery({
    queryKey: ["stage-policy", topicId, stageKey],
    queryFn: () => fetchStagePolicy(topicId, stageKey),
    enabled,
  });
  const summaryQ = useQuery({
    queryKey: ["stage-summary", topicId, stageKey],
    queryFn: () => fetchStageSummary(topicId, stageKey),
    enabled,
  });
  const artifactsQ = useQuery({
    queryKey: ["topic-artifacts", topicId],
    queryFn: () => fetchTopicArtifacts(topicId),
    enabled,
  });
  const eventsQ = useQuery({
    queryKey: ["topic-events", topicId],
    queryFn: () => fetchTopicEvents(topicId),
    enabled,
  });
  const decisionsQ = useQuery({
    queryKey: ["topic-decisions", topicId],
    queryFn: () => fetchTopicDecisions(topicId),
    enabled,
  });
  const rollbacksQ = useQuery({
    queryKey: ["topic-rollback-log-page", topicId],
    queryFn: () => fetchRollbackLog(topicId),
    enabled,
  });
  const rubricsQ = useQuery({
    queryKey: ["rubric-scores", topicId],
    queryFn: () => fetchRubricScores(topicId),
    enabled,
  });

  const rows: TraceRow[] = useMemo(() => {
    if (!stage) return [];
    const out: TraceRow[] = [];
    for (const p of primitivesQ.data?.primitives ?? []) {
      if (p.stage !== stage) continue;
      out.push({ kind: "primitive", at: p.started_at, data: p });
    }
    for (const e of eventsQ.data?.events ?? []) {
      if (e.stage !== stage) continue;
      out.push({ kind: "event", at: e.created_at, data: e });
    }
    for (const d of decisionsQ.data?.decisions ?? []) {
      if (d.stage !== stage) continue;
      out.push({ kind: "decision", at: d.created_at, data: d });
    }
    for (const r of rollbacksQ.data ?? []) {
      if (r.from_stage !== stage && r.to_stage !== stage) continue;
      out.push({ kind: "rollback", at: r.created_at, data: r });
    }
    return out.sort((a, b) => (a.at < b.at ? 1 : -1));
  }, [
    stage,
    primitivesQ.data,
    eventsQ.data,
    decisionsQ.data,
    rollbacksQ.data,
  ]);

  const stageArtifacts: Artifact[] = useMemo(() => {
    if (!stage) return [];
    const map = artifactsQ.data?.artifacts_by_stage ?? {};
    return map[stage] ?? [];
  }, [stage, artifactsQ.data]);

  const rubricByArtifact = useMemo(() => {
    const map = new Map<number, RubricScore>();
    for (const s of rubricsQ.data ?? []) {
      if (s.stage !== stage) continue;
      if (!map.has(s.artifact_id) || map.get(s.artifact_id)!.scored_at < s.scored_at) {
        map.set(s.artifact_id, s);
      }
    }
    return map;
  }, [rubricsQ.data, stage]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-[560px] lg:max-w-[640px]">
        <SheetHeader className="border-b px-5 py-4">
          <SheetTitle className="flex items-center gap-2">
            {stage ? STAGE_LABELS[stage] : ""}
            {policyQ.data?.policy?.risk_level && (
              <Badge variant="outline" className="text-[10px]">
                {policyQ.data.policy.risk_level} risk
              </Badge>
            )}
            {policyQ.data?.policy?.approval_policy && (
              <Badge variant="outline" className="text-[10px]">
                {policyQ.data.policy.approval_policy}
              </Badge>
            )}
          </SheetTitle>
          <SheetDescription className="text-xs">
            {policyQ.data?.policy?.description ||
              t("stage.drawer.description") ||
              "Inspect every primitive, decision, and invariant for this stage."}
          </SheetDescription>

          {/* Policy summary counts */}
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            <SummaryChip
              label={t("stage.drawer.summary.planned") || "planned"}
              value={summaryQ.data?.primitives_planned ?? 0}
            />
            <SummaryChip
              label={t("stage.drawer.summary.ran") || "ran"}
              value={summaryQ.data?.primitives_ran ?? 0}
              tone="emerald"
            />
            <SummaryChip
              label={t("stage.drawer.summary.skipped") || "skipped"}
              value={summaryQ.data?.primitives_skipped ?? 0}
              tone="slate"
            />
            <SummaryChip
              label={t("stage.drawer.summary.failed") || "failed"}
              value={summaryQ.data?.primitives_failed ?? 0}
              tone={summaryQ.data?.primitives_failed ? "red" : "slate"}
            />
            {(summaryQ.data?.invariant_violations_count ?? 0) > 0 && (
              <SummaryChip
                label={t("stage.drawer.summary.invariant") || "invariants"}
                value={summaryQ.data?.invariant_violations_count ?? 0}
                tone="red"
              />
            )}
            <span className="text-muted-foreground">
              · ${summaryQ.data?.total_cost_usd?.toFixed(3) ?? "0.000"} ·{" "}
              {(summaryQ.data?.total_tokens ?? 0).toLocaleString()} tok
            </span>
          </div>

          {/* Loopback counter */}
          {policyQ.data?.loopback_state?.rounds_used ? (
            <div className="mt-1 flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400">
              <RotateCcw className="size-3" />
              {t("stage.drawer.gate.loopback") || "rolled back"}{" "}
              {policyQ.data.loopback_state.rounds_used}/
              {policyQ.data.loopback_state.rounds_max || "?"}
              {policyQ.data.loopback_state.last_trigger && (
                <span className="text-muted-foreground">
                  · last: {policyQ.data.loopback_state.last_trigger}
                </span>
              )}
            </div>
          ) : null}

          {/* Invariant violations inline */}
          {(policyQ.data?.invariant_violations ?? []).length > 0 && (
            <ul className="mt-1 space-y-0.5 text-xs">
              {(policyQ.data?.invariant_violations ?? []).slice(0, 3).map((v, i) => (
                <li key={i} className="flex items-start gap-1.5 text-red-700 dark:text-red-400">
                  <AlertTriangle className="mt-0.5 size-3 shrink-0" />
                  <span className="break-words">{v.message}</span>
                </li>
              ))}
            </ul>
          )}
        </SheetHeader>

        <Tabs defaultValue="trace" className="flex min-h-0 flex-1 flex-col">
          <TabsList className="mx-5 mt-3 self-start">
            <TabsTrigger value="trace">
              {t("stage.drawer.trace") || "Trace"}
            </TabsTrigger>
            <TabsTrigger value="artifacts">
              {t("stage.drawer.artifacts") || "Artifacts"}{" "}
              <span className="ml-1 text-xs text-muted-foreground">
                ({stageArtifacts.length})
              </span>
            </TabsTrigger>
          </TabsList>
          <TabsContent value="trace" className="min-h-0 flex-1 overflow-hidden">
            <div className="h-full overflow-y-auto px-5 py-3">
              {primitivesQ.isPending || eventsQ.isPending ? (
                <TraceSkeleton />
              ) : rows.length === 0 ? (
                <p className="text-sm text-muted-foreground py-8 text-center">
                  {t("stage.drawer.emptyTrace") ||
                    "No activity recorded for this stage yet."}
                </p>
              ) : (
                <TraceList rows={rows} />
              )}
            </div>
          </TabsContent>
          <TabsContent value="artifacts" className="min-h-0 flex-1 overflow-hidden">
            <div className="h-full overflow-y-auto px-5 py-3">
              {artifactsQ.isPending ? (
                <ArtifactSkeleton />
              ) : stageArtifacts.length === 0 ? (
                <p className="text-sm text-muted-foreground py-8 text-center">
                  {t("stage.drawer.emptyArtifacts") ||
                    "No artifacts recorded for this stage yet."}
                </p>
              ) : (
                <ul className="space-y-2">
                  {stageArtifacts.map((a) => (
                    <ArtifactCard
                      key={a.id}
                      artifact={a}
                      rubric={rubricByArtifact.get(a.id)}
                    />
                  ))}
                </ul>
              )}
            </div>
          </TabsContent>
        </Tabs>

        {stage && (
          <StageRollbackFooter
            topicId={topicId}
            stage={stage}
            onDone={() => onOpenChange(false)}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------
// Trace list
// ---------------------------------------------------------------------------

function TraceList({ rows }: { rows: TraceRow[] }) {
  // Split into foreground vs background primitives: anything not in the
  // ARTIFACT_PRODUCING_HINT set and not a skip/event/decision is collapsed.
  const foreground: TraceRow[] = [];
  const background: TraceRow[] = [];
  for (const r of rows) {
    if (r.kind === "primitive") {
      const p = r.data;
      const hints =
        p.skipped ||
        !p.success ||
        ARTIFACT_PRODUCING_HINT.has(p.primitive) ||
        (p.cost_usd ?? 0) > 0.005 ||
        p.artifact_id;
      if (hints) foreground.push(r);
      else background.push(r);
    } else {
      foreground.push(r);
    }
  }

  const [showBg, setShowBg] = useState(false);

  return (
    <ul className="space-y-1.5">
      {foreground.map((r, i) => (
        <TraceRowView key={`${r.kind}-${i}-${r.at}`} row={r} />
      ))}
      {background.length > 0 && (
        <li>
          <button
            type="button"
            onClick={() => setShowBg((v) => !v)}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
          >
            {showBg ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
            + {background.length} background calls
          </button>
          {showBg && (
            <ul className="mt-1 space-y-1.5 border-l border-dashed pl-3">
              {background.map((r, i) => (
                <TraceRowView key={`bg-${i}-${r.at}`} row={r} compact />
              ))}
            </ul>
          )}
        </li>
      )}
    </ul>
  );
}

function TraceRowView({ row, compact }: { row: TraceRow; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  if (row.kind === "primitive") {
    return (
      <PrimitiveRow row={row.data} onToggle={() => setOpen((v) => !v)} open={open} compact={compact} />
    );
  }
  if (row.kind === "event") {
    return <EventRow event={row.data} />;
  }
  if (row.kind === "decision") {
    return <DecisionRow decision={row.data} />;
  }
  return <RollbackRow rollback={row.data} />;
}

function PrimitiveRow({
  row,
  onToggle,
  open,
  compact,
}: {
  row: PrimitiveExecution;
  onToggle: () => void;
  open: boolean;
  compact?: boolean;
}) {
  const producing = Boolean(row.artifact_id) || ARTIFACT_PRODUCING_HINT.has(row.primitive);
  const tokens = (row.prompt_tokens ?? 0) + (row.completion_tokens ?? 0);
  const toneBorder = row.skipped
    ? "border-l-slate-300"
    : !row.success
      ? "border-l-red-400"
      : producing
        ? "border-l-blue-400"
        : "border-l-slate-200";
  return (
    <li>
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          "flex w-full items-start gap-2 border-l-2 bg-muted/30 px-2.5 py-1.5 text-left transition-colors hover:bg-muted/50 rounded-r",
          toneBorder,
          compact && "text-xs"
        )}
      >
        <span className="mt-0.5 shrink-0 text-muted-foreground tabular-nums text-[10px]">
          {formatHM(row.started_at)}
        </span>
        <span className="shrink-0">
          {row.skipped ? (
            <SkipForward className="size-3.5 text-slate-400" />
          ) : row.success ? (
            <CheckCircle2 className="size-3.5 text-emerald-500" />
          ) : (
            <XCircle className="size-3.5 text-red-400" />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="font-medium text-[12px]">{row.primitive}</span>
          {row.model_used && row.model_used !== "none" && (
            <span className="text-muted-foreground"> · {row.model_used}</span>
          )}
          {!row.skipped && tokens > 0 && (
            <span className="text-muted-foreground"> · {tokens.toLocaleString()} tok</span>
          )}
          {!row.skipped && (row.cost_usd ?? 0) > 0 && (
            <span className="text-muted-foreground"> · ${row.cost_usd.toFixed(4)}</span>
          )}
          {row.retry_ordinal > 0 && (
            <Badge variant="outline" className="ml-1 text-[9px] h-4 px-1">
              retry {row.retry_ordinal}
            </Badge>
          )}
          {row.cache_hit && (
            <Badge variant="outline" className="ml-1 text-[9px] h-4 px-1">
              cache
            </Badge>
          )}
          {row.skipped && row.skip_reason && (
            <span className="ml-1 text-muted-foreground italic">
              skipped — {row.skip_reason}
            </span>
          )}
          {!row.success && row.error && (
            <p className="mt-0.5 truncate text-[11px] text-red-600">{row.error}</p>
          )}
        </span>
        {open ? (
          <ChevronDown className="mt-0.5 size-3 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="mt-0.5 size-3 shrink-0 text-muted-foreground" />
        )}
      </button>
      {open && (
        <dl className="ml-4 mt-1 space-y-0.5 rounded-md bg-muted/40 px-3 py-2 text-[11px]">
          <KeyVal k="backend" v={row.backend} />
          <KeyVal k="actor" v={row.actor} />
          <KeyVal k="origin" v={row.origin} />
          {row.parallel_group && <KeyVal k="parallel_group" v={row.parallel_group} />}
          {row.artifact_id != null && <KeyVal k="artifact_id" v={String(row.artifact_id)} />}
          <KeyVal k="started_at" v={row.started_at} />
          <KeyVal k="finished_at" v={row.finished_at} />
        </dl>
      )}
    </li>
  );
}

function EventRow({ event }: { event: StageEvent }) {
  const typeTone: Record<string, string> = {
    advance: "text-emerald-600",
    gate_check: "text-blue-600",
    artifact_record: "text-violet-600",
    decision: "text-amber-600",
  };
  return (
    <li className="flex items-start gap-2 border-l-2 border-l-dashed border-slate-300 px-2.5 py-1.5 text-[12px]">
      <span className="shrink-0 text-muted-foreground tabular-nums text-[10px]">
        {formatHM(event.created_at)}
      </span>
      <Clock className="size-3.5 shrink-0 text-muted-foreground" />
      <span className={cn("font-medium", typeTone[event.event_type] ?? "text-foreground")}>
        {event.event_type.replace(/_/g, " ")}
      </span>
      {event.actor && (
        <span className="text-muted-foreground">· {event.actor}</span>
      )}
    </li>
  );
}

function DecisionRow({ decision }: { decision: DecisionLogEntry }) {
  return (
    <li className="flex items-start gap-2 border-l-2 border-l-amber-300 bg-amber-50/40 dark:bg-amber-950/20 px-2.5 py-1.5 text-[12px]">
      <span className="shrink-0 text-muted-foreground tabular-nums text-[10px]">
        {formatHM(decision.created_at)}
      </span>
      <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-amber-600" />
      <span className="min-w-0 flex-1">
        <span className="font-medium">{decision.choice}</span>
        {decision.actor && (
          <span className="text-muted-foreground"> · {decision.actor}</span>
        )}
        {decision.reasoning && (
          <p className="mt-0.5 text-muted-foreground">{decision.reasoning}</p>
        )}
      </span>
    </li>
  );
}

function RollbackRow({ rollback }: { rollback: RollbackLogEntry }) {
  return (
    <li className="flex items-start gap-2 border-l-2 border-l-rose-400 bg-rose-50/40 dark:bg-rose-950/20 px-2.5 py-1.5 text-[12px]">
      <span className="shrink-0 text-muted-foreground tabular-nums text-[10px]">
        {formatHM(rollback.created_at)}
      </span>
      <RotateCcw className="mt-0.5 size-3.5 shrink-0 text-rose-500" />
      <span className="min-w-0 flex-1">
        <span className="font-medium">
          rollback {rollback.from_stage} → {rollback.to_stage}
        </span>
        {rollback.reason && (
          <p className="mt-0.5 text-muted-foreground">{rollback.reason}</p>
        )}
      </span>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Artifact card (tab 2)
// ---------------------------------------------------------------------------

function ArtifactCard({ artifact, rubric }: { artifact: Artifact; rubric?: RubricScore }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-md border bg-muted/30">
      <button
        type="button"
        className="flex w-full items-start gap-2 px-3 py-2 text-left text-[13px] hover:bg-muted/60 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <ChevronDown className="mt-0.5 size-3.5 text-muted-foreground" /> : <ChevronRight className="mt-0.5 size-3.5 text-muted-foreground" />}
        <FileText className="mt-0.5 size-3.5 text-muted-foreground" />
        <span className="min-w-0 flex-1">
          <span className="font-medium">{artifact.title || artifact.artifact_type}</span>
          <span className="ml-2 text-[10px] text-muted-foreground">{artifact.artifact_type}</span>
          {artifact.is_stale && (
            <Badge variant="destructive" className="ml-2 h-4 px-1 text-[9px]">
              stale
            </Badge>
          )}
          {rubric && (
            <span className="ml-2 text-[11px] text-muted-foreground font-mono">
              {rubric.weighted_total.toFixed(1)} ({rubric.verdict})
              {rubric.shadow_verdict && (
                <span className="ml-1 text-amber-600">
                  · would: {rubric.shadow_verdict}
                </span>
              )}
            </span>
          )}
        </span>
      </button>
      {open && artifact.payload && (
        <pre className="mx-3 mb-2 max-h-60 overflow-auto rounded bg-muted/70 p-2 text-[10.5px] text-muted-foreground whitespace-pre-wrap font-mono leading-relaxed">
          {JSON.stringify(artifact.payload, null, 2).slice(0, 2500)}
          {JSON.stringify(artifact.payload, null, 2).length > 2500 && "\n…"}
        </pre>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// Rollback footer
// ---------------------------------------------------------------------------

function StageRollbackFooter({
  topicId,
  stage,
  onDone,
}: {
  topicId: number;
  stage: ResearchStage;
  onDone: () => void;
}) {
  const qc = useQueryClient();
  const { t } = useT();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mut = useMutation({
    mutationFn: () => rollbackTopic(topicId, stage, reason),
    onSuccess: (result) => {
      if (result.success) {
        qc.invalidateQueries({ queryKey: ["topic", topicId] });
        qc.invalidateQueries({ queryKey: ["topic-rollback-log-page", topicId] });
        qc.invalidateQueries({ queryKey: ["stage-policy", topicId, stage] });
        qc.invalidateQueries({ queryKey: ["stage-summary", topicId, stage] });
        setReason("");
        onDone();
      } else {
        setError(result.error ?? "Rollback failed");
      }
    },
    onError: (err: Error) => setError(err.message),
  });

  return (
    <div className="border-t bg-muted/20 px-5 py-3">
      <label className="text-[11px] font-medium text-muted-foreground">
        {t("stage.drawer.rollback.prompt") || "Rollback reason"}
      </label>
      <textarea
        className="mt-1 w-full rounded-md border bg-background px-3 py-1.5 text-xs placeholder:text-muted-foreground focus:ring-2 focus:ring-rose-500/30 focus:outline-none"
        rows={2}
        placeholder={
          t("stage.drawer.rollback.placeholder") ||
          `Why are you rolling back to ${STAGE_LABELS[stage]}?`
        }
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      {error && <p className="mt-1 text-[11px] text-red-600">{error}</p>}
      <div className="mt-2 flex justify-end gap-2">
        <Button
          size="sm"
          variant="destructive"
          disabled={!reason.trim() || mut.isPending}
          onClick={() => mut.mutate()}
        >
          {mut.isPending ? (
            <>
              <Loader2 className="size-3 animate-spin" />
              Rolling back…
            </>
          ) : (
            <>
              <RotateCcw className="size-3" />
              Rollback to {STAGE_LABELS[stage]}
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small atoms
// ---------------------------------------------------------------------------

function SummaryChip({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "emerald" | "slate" | "red";
}) {
  const toneCls =
    tone === "emerald"
      ? "text-emerald-700 dark:text-emerald-400"
      : tone === "red"
        ? "text-red-700 dark:text-red-400"
        : "text-foreground";
  return (
    <span className="inline-flex items-center gap-1">
      <span className={cn("font-mono tabular-nums text-xs font-medium", toneCls)}>{value}</span>
      <span className="text-[11px] text-muted-foreground">{label}</span>
    </span>
  );
}

function KeyVal({ k, v }: { k: string; v: string | null | undefined }) {
  if (!v) return null;
  return (
    <div className="flex gap-2">
      <dt className="w-24 text-muted-foreground">{k}</dt>
      <dd className="min-w-0 flex-1 break-all font-mono">{v}</dd>
    </div>
  );
}

function TraceSkeleton() {
  return (
    <div className="space-y-2">
      {[0, 1, 2, 3].map((i) => (
        <Skeleton key={i} className="h-7 w-full" />
      ))}
    </div>
  );
}

function ArtifactSkeleton() {
  return (
    <div className="space-y-2">
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

function formatHM(iso: string | null | undefined): string {
  if (!iso) return "--:--";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso.slice(11, 16) || "--:--";
    return d.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "--:--";
  }
}
