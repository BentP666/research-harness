// ---------------------------------------------------------------------------
// Research Harness — shared TypeScript types
// These mirror the FastAPI backend models.
// ---------------------------------------------------------------------------

// -- Enums / union literals ------------------------------------------------

export type ResearchStage =
  | "init"
  | "build"
  | "analyze"
  | "propose"
  | "experiment"
  | "write";

export type GateType =
  | "approval_gate"
  | "coverage_gate"
  | "adversarial_gate"
  | "review_gate"
  | "integrity_gate"
  | "experiment_gate";

export type StageStatus =
  | "not_started"
  | "in_progress"
  | "blocked"
  | "completed"
  | "approved";

export type PaperRelevance = "high" | "medium" | "low";

export type ArtifactType =
  | "topic_frame"
  | "paper_pool"
  | "coverage_report"
  | "gap_analysis"
  | "evidence_matrix"
  | "direction_ranking"
  | "design_brief"
  | "algorithm_candidate"
  | "originality_check"
  | "research_proposal"
  | "experiment_result"
  | "writing_architecture"
  | "section_draft"
  | "review_report"
  | "adversarial_round"
  | "integrity_report"
  | "final_paper";

// -- Core entities ---------------------------------------------------------

export interface Domain {
  id: number;
  name: string;
  description: string | null;
  status: string;
  topic_count: number;
  created_at: string;
}

export interface Topic {
  id: number;
  name: string;
  description: string | null;
  status: string;
  domain_id: number | null;
  domain_name: string | null;
  paper_count: number;
  created_at: string;
  current_stage?: ResearchStage | null;
  stage_status?: string | null;
}

export interface TopicDetail extends Topic {
  status: string;
  target_venue: string;
  deadline: string;
  contributions: string;
  current_stage: ResearchStage | null;
  stage_status: string | null;
  gate_status: string | null;
  mode: string | null;
  stop_before: string | null;
  blocking_issue_count: number;
  unresolved_issue_count: number;
  annotation_count: number;
  artifact_counts: Record<string, number>;
}

// Shape of a paper row returned by GET /api/papers (list endpoint).
// The list endpoint selects p.* plus, when ?topic_id= is set, the per-topic
// pt.relevance value. Fields that are not selected by the backend are NOT
// included here (previous version of this type lied about topic_id /
// topic_name / source / ingested_at; those columns don't exist on /api/papers).
export interface Paper {
  id: number;
  title: string;
  authors: string[]; // backend always normalizes to a JSON array
  year: number | null;
  venue: string | null;
  arxiv_id: string | null;
  doi: string | null;
  s2_id: string | null;
  url: string | null;
  abstract: string | null;
  pdf_path: string | null;
  pdf_hash: string | null;
  citation_count: number | null;
  deep_read: boolean;
  status: string;
  created_at: string;
  // Only populated when the request was scoped via ?topic_id=
  relevance?: PaperRelevance | null;
}

// Shape of GET /api/papers/{id}. Matches the backend Pydantic PaperDetail.
export interface PaperDetail {
  id: number;
  title: string;
  authors: string[];
  year: number | null;
  venue: string;
  doi: string;
  arxiv_id: string;
  s2_id: string;
  url: string;
  abstract: string;
  citation_count: number | null;
  deep_read: boolean;
  status: string;
  pdf_path: string;
  created_at: string;
  annotations: PaperAnnotation[];
  topics: Array<{ id: number; name: string; relevance: PaperRelevance | null }>;
}

export interface PaperAnnotation {
  id: number;
  section: string;
  // Backend stores annotations as JSON; _parse_json_field falls back to the
  // raw string when content isn't valid JSON, so this can be either shape.
  content: string | Record<string, unknown> | unknown[];
  source: string | null;
  confidence: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface ReviewIssue {
  id: number;
  topic_id: number;
  review_type: string;
  severity: "critical" | "high" | "medium" | "low";
  category: string;
  summary: string;
  details: string | null;
  recommended_action: string | null;
  status: "open" | "in_progress" | "resolved" | "wontfix";
  blocking: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface TopicArtifactsResponse {
  topic_id: number;
  artifacts_by_stage: Record<string, Artifact[]>;
}

export interface TopicEventsResponse {
  topic_id: number;
  events: StageEvent[];
}

export interface TopicIssuesResponse {
  topic_id: number;
  issues: ReviewIssue[];
}

export interface Artifact {
  id: number;
  topic_id: number;
  stage: ResearchStage;
  artifact_type: ArtifactType | string;
  title: string | null;
  payload: Record<string, unknown> | null;
  is_stale: boolean;
  stale_reason: string | null;
  created_at: string;
}

export interface OrchestratorRun {
  id: number;
  topic_id: number;
  current_stage: ResearchStage;
  mode: string;
  stop_before: string | null;
  started_at: string;
  updated_at: string;
}

export interface StageEvent {
  id: number;
  topic_id: number;
  stage: ResearchStage;
  event_type: "advance" | "gate_check" | "artifact_record" | "decision";
  actor: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface StageEventFull {
  id: number;
  run_id: number;
  project_id: number;
  topic_id: number;
  from_stage: string;
  to_stage: string;
  event_type: "init" | "advance" | "transition" | "resume";
  status: string;
  gate_type: string;
  actor: string;
  rationale: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface DecisionLogEntry {
  id: number;
  project_id: number;
  topic_id: number;
  stage: string;
  checkpoint: string;
  choice: string;
  reasoning: string;
  params: Record<string, unknown>;
  created_at: string;
  actor?: string | null;
  origin?: string | null;
}

export interface TopicDecisionsResponse {
  topic_id: number;
  decisions: DecisionLogEntry[];
}

// -- Experiment iteration loop -------------------------------------------

export interface ExperimentBestRun {
  iteration: number;
  primary_metric_value: number | null;
  cost_usd: number;
  tokens_used: number;
}

export interface TopicExperiment {
  id: number;
  topic_id: number;
  name: string;
  task_description: string;
  primary_metric: string;
  direction: "max" | "min";
  mode: "strict" | "agent";
  status: "pending" | "running" | "completed" | "failed" | "stopped";
  stopped_reason: string | null;
  best_run_id: number | null;
  budget: {
    max_iterations?: number;
    max_cost_usd?: number;
    max_tokens?: number;
    patience?: number;
  };
  best: ExperimentBestRun | null;
  created_at: string;
  updated_at: string;
}

export interface TopicExperimentsResponse {
  topic_id: number;
  experiments: TopicExperiment[];
}

export interface ExperimentRunRow {
  id: number;
  iteration: number;
  code_hash: string;
  primary_metric_value: number | null;
  elapsed_sec: number;
  cost_usd: number;
  tokens_used: number;
  status: "completed" | "failed" | "timeout" | "invalid";
  returncode: number;
  stdout_tail: string;
  stderr_tail: string;
  feedback_to_next: string;
  created_at: string;
}

export interface ExperimentRunsResponse {
  experiment: {
    id: number;
    topic_id: number;
    name: string;
    primary_metric: string;
    direction: "max" | "min";
    mode: "strict" | "agent";
    status: string;
    stopped_reason: string | null;
    best_run_id: number | null;
  } | null;
  runs: ExperimentRunRow[];
}

// -- Analytics / dashboard -------------------------------------------------

export interface ProvenanceBackendRow {
  backend: string;
  model_used: string;
  call_count: number;
  total_cost: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface ProvenancePrimitiveRow {
  primitive: string;
  call_count: number;
  total_cost: number;
  prompt_tokens: number;
  completion_tokens: number;
  success_count: number;
  failure_count: number;
}

export interface ProvenanceRecentRecord {
  id: number;
  primitive: string;
  backend: string;
  model_used: string;
  cost_usd: number;
  prompt_tokens: number;
  completion_tokens: number;
  success: number;
  created_at: string;
}

export interface ProvenanceSummary {
  total_records: number;
  total_cost_usd: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  by_backend: ProvenanceBackendRow[];
  by_primitive: ProvenancePrimitiveRow[];
  recent_records: ProvenanceRecentRecord[];
}

export interface DashboardStats {
  total_papers: number;
  total_domains: number;
  total_topics: number;
  total_artifacts: number;
  total_provenance_records: number;
  papers_with_pdf: number;
  recent_papers: Array<Record<string, unknown>>;
  recent_events: Array<Record<string, unknown>>;
}

// -- Stage metadata (for UI rendering) -------------------------------------

export const RESEARCH_STAGES: readonly ResearchStage[] = [
  "init",
  "build",
  "analyze",
  "propose",
  "experiment",
  "write",
] as const;

export const STAGE_LABELS: Record<ResearchStage, string> = {
  init: "Init",
  build: "Build",
  analyze: "Analyze",
  propose: "Propose",
  experiment: "Experiment",
  write: "Write",
};

export const STAGE_COLORS: Record<ResearchStage, string> = {
  init: "bg-slate-500",
  build: "bg-blue-500",
  analyze: "bg-violet-500",
  propose: "bg-amber-500",
  experiment: "bg-emerald-500",
  write: "bg-rose-500",
};

export const STAGE_TEXT_COLORS: Record<ResearchStage, string> = {
  init: "text-slate-600 dark:text-slate-400",
  build: "text-blue-600 dark:text-blue-400",
  analyze: "text-violet-600 dark:text-violet-400",
  propose: "text-amber-600 dark:text-amber-400",
  experiment: "text-emerald-600 dark:text-emerald-400",
  write: "text-rose-600 dark:text-rose-400",
};

export const STAGE_BG_COLORS: Record<ResearchStage, string> = {
  init: "bg-slate-100 dark:bg-slate-900",
  build: "bg-blue-100 dark:bg-blue-900",
  analyze: "bg-violet-100 dark:bg-violet-900",
  propose: "bg-amber-100 dark:bg-amber-900",
  experiment: "bg-emerald-100 dark:bg-emerald-900",
  write: "bg-rose-100 dark:bg-rose-900",
};

export const STAGE_DESCRIPTIONS: Record<ResearchStage, string> = {
  init: "Environment sensing, topic framing, seed papers",
  build: "Literature retrieval, citation expansion, PDF acquisition",
  analyze: "Claim extraction, gap detection, direction ranking",
  propose: "Adversarial review, study design, algorithm design",
  experiment: "Code generation, sandbox execution, metric evaluation",
  write: "Section drafting, review loop, paper compilation",
};

export const STAGE_GATE_TYPES: Record<ResearchStage, GateType> = {
  init: "approval_gate",
  build: "coverage_gate",
  analyze: "approval_gate",
  propose: "adversarial_gate",
  experiment: "experiment_gate",
  write: "review_gate",
};

export const STAGE_ICONS: Record<ResearchStage, string> = {
  init: "Compass",
  build: "Library",
  analyze: "Search",
  propose: "Lightbulb",
  experiment: "FlaskConical",
  write: "PenTool",
};

// -- API response wrappers -------------------------------------------------

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// -- v2: Agent model -------------------------------------------------------

export type AgentRole = "generator" | "challenger" | "judge";

export interface Agent {
  id: number;
  nickname: string;
  provider: string;
  provider_family: string;
  model: string;
  api_key_env: string;
  role_prefs: Record<string, boolean>;
  monthly_budget_usd: number | null;
  status: "active" | "paused" | "archived";
  created_at: string;
}

export interface AgentPairing {
  id: number;
  name: string;
  generator_agent_id: number;
  judge_agent_id: number;
  challenger_agent_id: number | null;
  topic_id: number | null;
  is_global_default: number;
  generator_name: string;
  generator_provider: string;
  generator_model: string;
  judge_name: string;
  judge_provider: string;
  judge_model: string;
  challenger_name: string | null;
  challenger_provider: string | null;
  challenger_model: string | null;
  created_at: string;
}

export interface AgentPreset {
  id: string;
  name: string;
  description: string;
  agents: Array<{
    nickname: string;
    provider: string;
    model: string;
    api_key_env: string;
    role_prefs: Record<string, boolean>;
  }>;
}

export interface UserPreferences {
  language: string;
  discipline: string;
  default_venue_tier: string;
  default_quality_tier: string;
  default_autonomy: string;
  monthly_budget_cap_usd: number;
  onboarding_complete: number;
  auto_rollback_live: number; // 0 = shadow (default), 1 = live
}

export interface Calibration {
  stage: string;
  tier: string;
  threshold: number;
  false_rollback_rate: number | null;
  reject_rate: number | null;
  anchor_count: number;
  calibrated_at: string;
}

export interface CalibrationRunResult {
  count: number;
  results: Array<{
    stage: string;
    tier: string;
    threshold: number;
    anchor_count: number;
    false_rollback_rate: number;
    reject_rate: number;
    used_default: boolean;
  }>;
}

export interface TrendsRefreshResult {
  tier: string;
  dry_run: boolean;
  cluster_count: number;
  clusters: Array<{
    name: string;
    publishability_score: number;
    velocity_yoy: number;
  }>;
}

export type AutonomyLevel = "L0" | "L1" | "L2" | "L3";
export type QualityTier = "economy" | "standard" | "premium";
export type VenueTier = "A" | "B" | "workshop";
