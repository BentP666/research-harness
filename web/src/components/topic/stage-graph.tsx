"use client";

import { useMemo } from "react";
import { CornerDownLeft } from "lucide-react";
import {
  RESEARCH_STAGES,
  STAGE_LABELS,
  type ResearchStage,
} from "@/lib/types";
import type { RollbackLogEntry } from "@/lib/api";
import type { DecisionLogEntry } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n-provider";

type NodeStatus =
  | "completed"
  | "current"
  | "future"
  | "failed"
  | "idle";

const BLOCKED_STATUSES = new Set([
  "blocked",
  "failed",
  "needs_review",
  "waiting_human",
  "needs_human",
  "rollback",
]);

const IDLE_STATUSES = new Set([
  "paused",
  "stopped",
  "idle",
  "pending",
  "",
]);

interface StageEventLike {
  from_stage: string | null;
  to_stage: string | null;
  created_at: string;
  event_type?: string;
}

export interface StageGraphSummary {
  ran: number;
  planned: number;
  invariantViolations: number;
  /** Soft-completion signal — count of artifacts/claims/gaps for this stage
   * when no orchestrator primitive ran (legacy / backfilled work). */
  evidenceCount?: number;
}

interface StageGraphProps {
  currentStage: ResearchStage | null | undefined;
  stageStatus: string | null | undefined;
  events?: StageEventLike[];
  decisions?: DecisionLogEntry[];
  rollbacks?: RollbackLogEntry[];
  /** Per-stage summary counts (from /api/topics/{id}/stage-summary). Optional. */
  summaries?: Partial<Record<ResearchStage, StageGraphSummary>>;
  /** Fired when the user clicks / activates a node. Enables drilldown UI. */
  onNodeClick?: (stage: ResearchStage) => void;
  /** Which node currently has UI focus (e.g. drawer open). */
  selectedStage?: ResearchStage | null;
}

// Layout constants
const NODE_R = 18;
const FORWARD_Y = 48;
const X_STEP = 120;
const X_OFFSET = 60;
const WIDTH = X_OFFSET * 2 + (RESEARCH_STAGES.length - 1) * X_STEP;
const TOTAL_HEIGHT = 200;

function stageX(stage: string): number {
  const idx = RESEARCH_STAGES.indexOf(stage as ResearchStage);
  if (idx < 0) return -1;
  return X_OFFSET + idx * X_STEP;
}

const STAGE_TONE: Record<ResearchStage, { fill: string; ring: string; text: string }> = {
  init: { fill: "#f8fafc", ring: "#94a3b8", text: "#334155" },
  build: { fill: "#eff6ff", ring: "#3b82f6", text: "#1d4ed8" },
  analyze: { fill: "#faf5ff", ring: "#a855f7", text: "#7e22ce" },
  propose: { fill: "#fffbeb", ring: "#f59e0b", text: "#b45309" },
  experiment: { fill: "#ecfdf5", ring: "#10b981", text: "#047857" },
  write: { fill: "#fff1f2", ring: "#f43f5e", text: "#be123c" },
};

export function StageGraph({
  currentStage,
  stageStatus,
  events = [],
  decisions = [],
  rollbacks = [],
  summaries,
  onNodeClick,
  selectedStage,
}: StageGraphProps) {
  const { t } = useT();
  const currentIdx = currentStage ? RESEARCH_STAGES.indexOf(currentStage) : -1;
  const normalized = (stageStatus ?? "").toLowerCase();

  const nodeStatus: Record<ResearchStage, NodeStatus> = useMemo(() => {
    const out: Record<string, NodeStatus> = {};
    for (let i = 0; i < RESEARCH_STAGES.length; i++) {
      const s = RESEARCH_STAGES[i];
      if (currentIdx < 0) out[s] = "future";
      else if (i < currentIdx) out[s] = "completed";
      else if (i === currentIdx) {
        if (normalized === "completed" || normalized === "approved") out[s] = "completed";
        else if (BLOCKED_STATUSES.has(normalized)) out[s] = "failed";
        else if (IDLE_STATUSES.has(normalized)) out[s] = "idle";
        else if (normalized === "running" || normalized === "in_progress") out[s] = "current";
        else out[s] = "idle";
      } else out[s] = "future";
    }
    return out as Record<ResearchStage, NodeStatus>;
  }, [currentIdx, normalized]);

  // Build rollback arcs from rollback_log (explicit) + loopback transitions.
  const arcs = useMemo(() => {
    type Arc = {
      from: ResearchStage;
      to: ResearchStage;
      kind: "rollback" | "loopback";
      count: number;
      createdAt?: string;
    };
    const byKey = new Map<string, Arc>();

    for (const r of rollbacks) {
      const from = r.from_stage as ResearchStage | null;
      const to = r.to_stage as ResearchStage | null;
      if (!from || !to || from === to) continue;
      if (RESEARCH_STAGES.indexOf(to) >= RESEARCH_STAGES.indexOf(from)) continue;
      const key = `rollback:${from}->${to}`;
      const existing = byKey.get(key);
      if (existing) existing.count += 1;
      else byKey.set(key, { from, to, kind: "rollback", count: 1, createdAt: r.created_at });
    }
    for (const e of events) {
      if (e.event_type !== "transition") continue;
      const from = e.from_stage as ResearchStage | null;
      const to = e.to_stage as ResearchStage | null;
      if (!from || !to || from === to) continue;
      const fi = RESEARCH_STAGES.indexOf(from);
      const ti = RESEARCH_STAGES.indexOf(to);
      if (fi < 0 || ti < 0 || ti >= fi) continue;
      const key = `loopback:${from}->${to}`;
      const existing = byKey.get(key);
      if (existing) existing.count += 1;
      else byKey.set(key, { from, to, kind: "loopback", count: 1, createdAt: e.created_at });
    }
    return Array.from(byKey.values());
  }, [rollbacks, events]);

  const decisionCountByStage = useMemo(() => {
    const out: Record<string, number> = {};
    for (const d of decisions) {
      if (!d.stage) continue;
      out[d.stage] = (out[d.stage] ?? 0) + 1;
    }
    return out;
  }, [decisions]);

  return (
    <div className="space-y-2">
      <header className="flex items-center gap-2 text-xs text-muted-foreground">
        <CornerDownLeft className="size-3.5" />
        <span>
          {t("roadmap.graphHint") ||
            "Forward line = pipeline progress. Curved arcs below = rollbacks & loopbacks."}
        </span>
      </header>
      <div className="w-full overflow-x-auto">
        <svg
          viewBox={`0 0 ${WIDTH} ${TOTAL_HEIGHT}`}
          className="h-44 w-full min-w-[720px]"
          role="img"
          aria-label="Pipeline stage graph"
        >
          <defs>
            <marker
              id="arrow-forward"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
            </marker>
            <marker
              id="arrow-rollback"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#e11d48" />
            </marker>
            <marker
              id="arrow-loopback"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#d97706" />
            </marker>
          </defs>

          {/* Forward spine between adjacent stages */}
          {RESEARCH_STAGES.slice(0, -1).map((s, i) => {
            const next = RESEARCH_STAGES[i + 1];
            const x1 = stageX(s) + NODE_R;
            const x2 = stageX(next) - NODE_R;
            const completed = nodeStatus[s] === "completed";
            return (
              <line
                key={`fwd-${s}`}
                x1={x1}
                x2={x2}
                y1={FORWARD_Y}
                y2={FORWARD_Y}
                stroke={completed ? "#10b981" : "#cbd5e1"}
                strokeWidth={completed ? 3 : 2}
                strokeDasharray={completed ? "" : "4 3"}
                markerEnd="url(#arrow-forward)"
              />
            );
          })}

          {/* Rollback / loopback arcs below the spine */}
          {arcs.map((arc, i) => {
            const x1 = stageX(arc.from);
            const x2 = stageX(arc.to);
            // Offset multi-arcs vertically so they don't stack on top of each other.
            const depth =
              70 +
              (arcs.filter((a) => a.from === arc.from && a.to === arc.to).indexOf(
                arc
              )) *
                16 +
              i * 2;
            const midX = (x1 + x2) / 2;
            const d = `M ${x1} ${FORWARD_Y + NODE_R - 4} Q ${midX} ${FORWARD_Y + depth} ${x2} ${FORWARD_Y + NODE_R - 4}`;
            const color = arc.kind === "rollback" ? "#e11d48" : "#d97706";
            const marker =
              arc.kind === "rollback"
                ? "url(#arrow-rollback)"
                : "url(#arrow-loopback)";
            return (
              <g key={`arc-${arc.from}->${arc.to}-${arc.kind}`}>
                <path
                  d={d}
                  stroke={color}
                  strokeWidth={2}
                  fill="none"
                  strokeDasharray={arc.kind === "loopback" ? "5 3" : ""}
                  markerEnd={marker}
                  opacity={0.75}
                />
                <text
                  x={midX}
                  y={FORWARD_Y + depth + 4}
                  textAnchor="middle"
                  className="fill-current text-[10px]"
                  style={{ fill: color, fontWeight: 500 }}
                >
                  {arc.count > 1 ? `×${arc.count}` : ""}
                </text>
              </g>
            );
          })}

          {/* Stage nodes */}
          {RESEARCH_STAGES.map((s, idx) => {
            const x = stageX(s);
            const status = nodeStatus[s];
            const tone = STAGE_TONE[s];
            const isCurrent = status === "current";
            const isSelected = selectedStage === s;
            const ring =
              status === "completed"
                ? "#10b981"
                : status === "current"
                  ? "#6366f1"
                  : status === "failed"
                    ? "#dc2626"
                    : status === "idle"
                      ? "#f59e0b"
                      : tone.ring;
            const decCount = decisionCountByStage[s] ?? 0;
            const summary = summaries?.[s];
            const clickable = typeof onNodeClick === "function";
            return (
              <g
                key={s}
                role={clickable ? "button" : undefined}
                tabIndex={clickable ? 0 : undefined}
                aria-label={`${STAGE_LABELS[s]} stage`}
                aria-pressed={isSelected || undefined}
                onClick={() => onNodeClick?.(s)}
                onKeyDown={(e) => {
                  if (!clickable) return;
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onNodeClick?.(s);
                  } else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                    e.preventDefault();
                    const dir = e.key === "ArrowRight" ? 1 : -1;
                    const next = RESEARCH_STAGES[idx + dir];
                    if (next) onNodeClick?.(next);
                  }
                }}
                style={{
                  cursor: clickable ? "pointer" : "default",
                  outline: "none",
                }}
                className={clickable ? "focus-visible:[&>circle]:stroke-foreground" : undefined}
              >
                {isCurrent && (
                  <circle
                    cx={x}
                    cy={FORWARD_Y}
                    r={NODE_R + 4}
                    fill="none"
                    stroke={ring}
                    strokeWidth={2}
                    opacity={0.35}
                    style={{
                      transformOrigin: `${x}px ${FORWARD_Y}px`,
                      animation: "rh-pulse-ring 2s ease-in-out infinite",
                    }}
                  />
                )}
                {isSelected && (
                  <circle
                    cx={x}
                    cy={FORWARD_Y}
                    r={NODE_R + 6}
                    fill="none"
                    stroke="#0f172a"
                    strokeWidth={1.5}
                    opacity={0.6}
                  />
                )}
                <circle
                  cx={x}
                  cy={FORWARD_Y}
                  r={NODE_R}
                  fill={tone.fill}
                  stroke={ring}
                  strokeWidth={status === "future" ? 1.5 : 2.5}
                />
                <text
                  x={x}
                  y={FORWARD_Y + 4}
                  textAnchor="middle"
                  className="pointer-events-none text-[11px] font-semibold"
                  style={{ fill: tone.text }}
                >
                  {s[0].toUpperCase()}
                </text>
                <text
                  x={x}
                  y={FORWARD_Y + NODE_R + 14}
                  textAnchor="middle"
                  className="pointer-events-none text-[10px]"
                  style={{ fill: "#475569" }}
                >
                  {STAGE_LABELS[s]}
                </text>
                {/* ran/planned chip OR soft-completion evidence chip (top-right) */}
                {summary && summary.planned > 0 ? (() => {
                  const hasRun = summary.ran > 0;
                  const hasEvidence = (summary.evidenceCount ?? 0) > 0;
                  // Show evidence chip when no primitives ran but historical
                  // work exists (legacy/backfilled topics). Use indigo to
                  // distinguish from the slate "real run" chip.
                  const isSoft = !hasRun && hasEvidence;
                  const label = isSoft
                    ? `${summary.evidenceCount}`
                    : `${summary.ran}/${summary.planned}`;
                  const chipFill = isSoft ? "#6366f1" : "#1e293b";
                  const width = isSoft ? Math.max(20, label.length * 6 + 10) : 28;
                  return (
                    <g className="pointer-events-none">
                      <rect
                        x={x + NODE_R - 10}
                        y={FORWARD_Y - NODE_R - 6}
                        rx={6}
                        ry={6}
                        width={width}
                        height={13}
                        fill={chipFill}
                      />
                      <text
                        x={x + NODE_R - 10 + width / 2}
                        y={FORWARD_Y - NODE_R + 3}
                        textAnchor="middle"
                        fontSize="8.5"
                        fontWeight="600"
                        fill="white"
                      >
                        {label}
                      </text>
                    </g>
                  );
                })() : decCount > 0 ? (
                  <g className="pointer-events-none">
                    <circle
                      cx={x + NODE_R - 3}
                      cy={FORWARD_Y - NODE_R + 3}
                      r={8}
                      fill="#4f46e5"
                    />
                    <text
                      x={x + NODE_R - 3}
                      y={FORWARD_Y - NODE_R + 6}
                      textAnchor="middle"
                      fontSize="9"
                      fontWeight="600"
                      fill="white"
                    >
                      {decCount}
                    </text>
                  </g>
                ) : null}
                {/* invariant violation red dot, bottom-right */}
                {summary && summary.invariantViolations > 0 && (
                  <g className="pointer-events-none">
                    <circle
                      cx={x + NODE_R - 2}
                      cy={FORWARD_Y + NODE_R - 2}
                      r={7}
                      fill="#dc2626"
                    />
                    <text
                      x={x + NODE_R - 2}
                      y={FORWARD_Y + NODE_R + 1.5}
                      textAnchor="middle"
                      fontSize="9"
                      fontWeight="700"
                      fill="white"
                    >
                      {summary.invariantViolations}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend */}
      <footer className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
        <LegendSwatch color="#10b981" label={t("roadmap.legend.completed") || "completed"} />
        <LegendSwatch color="#6366f1" label={t("roadmap.legend.current") || "in progress"} />
        <LegendSwatch color="#f59e0b" label={t("roadmap.legend.idle") || "paused"} />
        <LegendSwatch color="#dc2626" label={t("roadmap.legend.failed") || "blocked"} />
        <LegendArc color="#e11d48" label={t("roadmap.legend.rollback") || "rollback"} />
        <LegendArc
          color="#d97706"
          dashed
          label={t("roadmap.legend.loopback") || "loopback"}
        />
      </footer>
    </div>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span
        className={cn("inline-block size-2.5 rounded-full")}
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}

function LegendArc({
  color,
  label,
  dashed,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1">
      <svg width="20" height="8" viewBox="0 0 20 8">
        <path
          d="M 2 6 Q 10 -2 18 6"
          stroke={color}
          strokeWidth={1.5}
          fill="none"
          strokeDasharray={dashed ? "3 2" : ""}
        />
      </svg>
      {label}
    </span>
  );
}
