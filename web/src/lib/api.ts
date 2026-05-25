// ---------------------------------------------------------------------------
// Research Harness — typed API client
// Calls FastAPI backend at http://localhost:8000
// ---------------------------------------------------------------------------

import type {
  Domain,
  Topic,
  TopicDetail,
  Paper,
  PaperDetail,
  DashboardStats,
  ProvenanceSummary,
  PaginatedResponse,
  TopicArtifactsResponse,
  TopicEventsResponse,
  TopicIssuesResponse,
  Agent,
  AgentPairing,
  AgentPreset,
  UserPreferences,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const LONGTASK_ADMIN_TOKEN = process.env.NEXT_PUBLIC_LONGTASK_ADMIN_TOKEN ?? "";

/** Direct URL of the streamed PDF for a paper — useful for <a href> downloads
 *  or <iframe src> embedding. Returns 404 when no PDF is on file. */
export function paperPdfUrl(paperId: number): string {
  return `${API_BASE}/api/papers/${paperId}/pdf`;
}

// ---------------------------------------------------------------------------
// LLM explain — used by the in-app PDF reader's selection toolbar
// ---------------------------------------------------------------------------

export type ExplainPreset =
  | "explain"
  | "summarize"
  | "translate_zh"
  | "critique";

export interface ExplainRequest {
  text: string;
  preset?: ExplainPreset;
  custom_prompt?: string;
  paper_title?: string;
  paper_id?: number;
  tier?: "light" | "medium" | "heavy";
}

export interface ExplainResponse {
  response: string;
  preset_used: ExplainPreset | null;
  tier: "light" | "medium" | "heavy";
  usage: {
    provider: string | null;
    model: string | null;
    prompt_tokens: number | null;
    completion_tokens: number | null;
  } | null;
}

export function explainSelection(
  body: ExplainRequest,
): Promise<ExplainResponse> {
  return apiFetch<ExplainResponse>("/api/llm/explain", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Codex LongTask Supervisor
// ---------------------------------------------------------------------------

export interface LongTaskRunSummary {
  id: string;
  title: string;
  objective?: string;
  status: string;
  max_workers: number;
  created_at: string;
  updated_at: string;
  task_count?: number;
  complete_count?: number;
  pending_gate_count?: number;
}

export interface LongTaskTask {
  id: string;
  run_id?: string;
  title: string;
  status: string;
  summary: string;
  dependencies?: string[];
  write_scope?: string[];
  risk_level?: string;
}

export interface LongTaskGate {
  id: string;
  run_id?: string;
  task_id?: string | null;
  gate_type: string;
  title: string;
  status: string;
  token_required?: boolean;
  decision?: string | null;
  note?: string | null;
  actor?: string | null;
  notification?: LongTaskGateNotification;
}

export interface LongTaskGateNotification {
  gate_id: string;
  run_id: string;
  task_id?: string | null;
  gate_type: string;
  title: string;
  status: string;
  expires_at: number;
  action_url: string;
  actions: Record<
    string,
    {
      label: string;
      decision: string;
      method: string;
      url: string;
    }
  >;
}

export interface LongTaskRunDetail {
  run: LongTaskRunSummary & { objective: string };
  tasks: LongTaskTask[];
  gates: LongTaskGate[];
  attempts: Array<Record<string, unknown>>;
  events: Array<Record<string, unknown>>;
}

export function fetchLongTaskRuns(): Promise<LongTaskRunSummary[]> {
  return apiFetch<LongTaskRunSummary[]>("/api/longtasks/runs");
}

export function fetchLongTaskRun(runId: string): Promise<LongTaskRunDetail> {
  return apiFetch<LongTaskRunDetail>(`/api/longtasks/runs/${runId}`);
}

export function createLongTaskGate(
  runId: string,
  body: {
    title: string;
    task_id?: string | null;
    gate_type?: string;
    token?: string;
  }
): Promise<LongTaskGate> {
  return apiFetch(`/api/longtasks/runs/${runId}/gates`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function decideLongTaskGate(
  gateId: string,
  body: {
    decision: "approved" | "rejected" | "paused" | "replan_requested";
    actor: string;
    token?: string;
    note?: string;
  }
): Promise<{ accepted: boolean; gate_id: string; status: string; message: string }> {
  return apiFetch(`/api/longtasks/gates/${gateId}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function dispatchLongTaskRun(
  runId: string,
  body: { limit?: number; execute?: boolean } = {}
): Promise<{ run_id: string; dispatched: number; results: Array<Record<string, unknown>> }> {
  return apiFetch(`/api/longtasks/runs/${runId}/dispatch`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function superviseLongTaskRun(
  runId: string,
  body: { max_cycles?: number; limit_per_cycle?: number; execute?: boolean } = {}
): Promise<{
  run_id: string;
  cycles: number;
  dispatched: number;
  stop_reason: string;
  status: string;
}> {
  return apiFetch(`/api/longtasks/runs/${runId}/supervise`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Generic fetcher
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (path.startsWith("/api/longtasks") && LONGTASK_ADMIN_TOKEN) {
    headers.set("X-LongTask-Token", LONGTASK_ADMIN_TOKEN);
  }
  const res = await fetch(url, {
    ...init,
    headers,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${res.statusText} — ${body}`);
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Domains
// ---------------------------------------------------------------------------

export function fetchDomains(): Promise<Domain[]> {
  return apiFetch<Domain[]>("/api/domains");
}

export function fetchDomain(domainId: number): Promise<Domain> {
  return apiFetch<Domain>(`/api/domains/${domainId}`);
}

export function createDomain(data: {
  name: string;
  description?: string;
}): Promise<Domain> {
  return apiFetch<Domain>("/api/domains", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateDomain(
  domainId: number,
  data: {
    name?: string;
    description?: string;
    status?: string;
  }
): Promise<Domain> {
  return apiFetch<Domain>(`/api/domains/${domainId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Topics
// ---------------------------------------------------------------------------

export function fetchTopics(params?: {
  domain_id?: number;
}): Promise<Topic[]> {
  const sp = new URLSearchParams();
  if (params?.domain_id != null) sp.set("domain_id", String(params.domain_id));
  const qs = sp.toString();
  return apiFetch<Topic[]>(`/api/topics${qs ? `?${qs}` : ""}`);
}

export function fetchTopic(topicId: number): Promise<Topic> {
  return apiFetch<Topic>(`/api/topics/${topicId}`);
}

export function fetchTopicDetail(topicId: number): Promise<TopicDetail> {
  return apiFetch<TopicDetail>(`/api/topics/${topicId}`);
}

export function fetchTopicPapers(
  topicId: number,
  params?: { page?: number; page_size?: number; search?: string }
): Promise<PaginatedResponse<Paper>> {
  const sp = new URLSearchParams();
  if (params?.page != null) sp.set("page", String(params.page));
  if (params?.page_size != null) sp.set("per_page", String(params.page_size));
  if (params?.search) sp.set("search", params.search);
  const qs = sp.toString();
  return apiFetch<PaginatedResponse<Paper>>(
    `/api/topics/${topicId}/papers${qs ? `?${qs}` : ""}`
  );
}

export function fetchTopicArtifacts(
  topicId: number
): Promise<TopicArtifactsResponse> {
  return apiFetch<TopicArtifactsResponse>(
    `/api/topics/${topicId}/artifacts`
  );
}

export function fetchTopicEvents(
  topicId: number
): Promise<TopicEventsResponse> {
  return apiFetch<TopicEventsResponse>(
    `/api/topics/${topicId}/events`
  );
}

export function fetchTopicDecisions(
  topicId: number
): Promise<import("./types").TopicDecisionsResponse> {
  return apiFetch(`/api/topics/${topicId}/decisions`);
}

// --- Audit drilldown (PR 1 / migration 055) --------------------------------

export interface PrimitiveExecution {
  id: number;
  primitive: string;
  category: string;
  stage: string;
  started_at: string;
  finished_at: string;
  backend: string;
  model_used: string;
  cost_usd: number;
  success: boolean;
  error: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  loop_round: number;
  actor: string | null;
  origin: string | null;
  retry_ordinal: number;
  cache_hit: boolean;
  parallel_group: string | null;
  skipped: boolean;
  skip_reason: string | null;
  artifact_id: number | null;
  quality_score: number | null;
  created_at: string;
}

export interface StagePolicySnapshot {
  topic_id: number;
  stage: string;
  policy: {
    name: string;
    tools: string[];
    codex: string;
    codex_focus: string;
    human_checkpoint: string;
    retry: string;
    max_codex_rounds: number;
    description: string;
    autonomous_allowed: boolean;
    risk_level: string;
    approval_policy: string;
    expansion_paper_budget: number;
  };
  invariant_violations: Array<{
    check: string;
    severity: string;
    message: string;
    artifact_id: number | null;
  }>;
  loopback_state: {
    rounds_used: number;
    rounds_max: number;
    last_trigger: string | null;
  };
}

export interface StageSummary {
  topic_id: number;
  stage: string;
  primitives_planned: number;
  primitives_ran: number;
  primitives_skipped: number;
  primitives_failed: number;
  total_tokens: number;
  total_cost_usd: number;
  duration_sec: number;
  invariant_violations_count: number;
  rubric: {
    weighted_total: number;
    verdict: string;
    shadow_verdict: string | null;
    scored_at: string;
  } | null;
  /** Soft-completion signal — non-zero when historic work exists (claims,
   * gaps, artifacts) even though no orchestrator primitive ran on this stage. */
  evidence_count?: number;
  evidence_breakdown?: {
    artifacts?: number;
    papers?: number;
    claims?: number;
    gaps?: number;
  };
}

export function fetchStagePrimitives(
  topicId: number,
  stage: string
): Promise<{ topic_id: number; stage: string; primitives: PrimitiveExecution[] }> {
  return apiFetch(
    `/api/topics/${topicId}/primitives?stage=${encodeURIComponent(stage)}`
  );
}

export function fetchStagePolicy(
  topicId: number,
  stage: string
): Promise<StagePolicySnapshot> {
  return apiFetch(`/api/topics/${topicId}/stage-policy/${encodeURIComponent(stage)}`);
}

export function fetchStageSummary(
  topicId: number,
  stage: string
): Promise<StageSummary> {
  return apiFetch(`/api/topics/${topicId}/stage-summary/${encodeURIComponent(stage)}`);
}

export function fetchTopicExperiments(
  topicId: number
): Promise<import("./types").TopicExperimentsResponse> {
  return apiFetch(`/api/topics/${topicId}/experiments`);
}

export function fetchExperimentRuns(
  experimentId: number
): Promise<import("./types").ExperimentRunsResponse> {
  return apiFetch(`/api/experiments/${experimentId}/runs`);
}

export interface CreateExperimentRequest {
  name?: string;
  task_description: string;
  fixture_files?: Record<string, string>;
  mutable_entry?: string;
  primary_metric: string;
  direction?: "max" | "min";
  mode?: "strict" | "agent";
  timeout_sec?: number;
  env_vars?: Record<string, string>;
  max_iterations?: number;
  max_cost_usd?: number;
  max_tokens?: number;
  patience?: number;
}

export interface CreateExperimentResponse {
  experiment_id: number;
  total_iterations: number;
  best_iteration: number | null;
  best_value: number | null;
  best_run_id: number | null;
  stopped_reason: string;
  total_cost_usd: number;
  total_tokens: number;
}

export function createTopicExperiment(
  topicId: number,
  body: CreateExperimentRequest
): Promise<CreateExperimentResponse> {
  return apiFetch(`/api/topics/${topicId}/experiments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function fetchTopicIssues(
  topicId: number
): Promise<TopicIssuesResponse> {
  return apiFetch<TopicIssuesResponse>(
    `/api/topics/${topicId}/issues`
  );
}

// ---------------------------------------------------------------------------
// Papers (global)
// ---------------------------------------------------------------------------

export async function fetchPapers(params?: {
  page?: number;
  page_size?: number;
  search?: string;
  topic_id?: number;
  domain_id?: number;
  status?: string;
  sort?: string;
  order?: "asc" | "desc";
}): Promise<PaginatedResponse<Paper>> {
  const sp = new URLSearchParams();
  if (params?.page != null) sp.set("page", String(params.page));
  if (params?.page_size != null)
    sp.set("per_page", String(params.page_size));
  if (params?.search) sp.set("search", params.search);
  if (params?.topic_id != null) sp.set("topic_id", String(params.topic_id));
  if (params?.domain_id != null) sp.set("domain_id", String(params.domain_id));
  if (params?.status) sp.set("status", params.status);
  if (params?.sort) sp.set("sort", params.sort);
  if (params?.order) sp.set("order", params.order);
  const qs = sp.toString();

  // Backend returns { data: Paper[], pagination: { page, per_page, total, total_pages } }
  const result = await apiFetch<{
    data: Paper[];
    pagination: { page: number; per_page: number; total: number; total_pages: number };
  }>(`/api/papers${qs ? `?${qs}` : ""}`);

  return {
    items: result.data,
    total: result.pagination.total,
    page: result.pagination.page,
    page_size: result.pagination.per_page,
  };
}

export function fetchPaper(paperId: number): Promise<PaperDetail> {
  return apiFetch<PaperDetail>(`/api/papers/${paperId}`);
}

export function toggleDeepRead(paperId: number, deepRead: boolean): Promise<{ success: boolean; deep_read: boolean }> {
  return apiFetch(`/api/papers/${paperId}/deep-read`, {
    method: "PATCH",
    body: JSON.stringify({ deep_read: deepRead }),
  });
}

export function enrichPaper(paperId: number): Promise<{ paper_id: number; fields_updated: Record<string, string> }> {
  return apiFetch(`/api/papers/${paperId}/enrich`, { method: "POST" });
}

export function enrichBatch(params?: {
  topic_id?: number;
  missing_fields?: string[];
  limit?: number;
}): Promise<{ status: string; limit: number; missing_fields: string[] }> {
  return apiFetch("/api/papers/enrich-batch", {
    method: "POST",
    body: JSON.stringify({
      topic_id: params?.topic_id,
      missing_fields: params?.missing_fields ?? ["venue", "citation_count"],
      limit: params?.limit ?? 50,
    }),
  });
}

// ---------------------------------------------------------------------------
// Dashboard / analytics
// ---------------------------------------------------------------------------

export function fetchDashboardStats(): Promise<DashboardStats> {
  return apiFetch<DashboardStats>("/api/stats");
}

export function fetchProvenanceSummary(
  topicId?: number
): Promise<ProvenanceSummary> {
  const path = topicId != null
    ? `/api/provenance/summary?topic_id=${topicId}`
    : "/api/provenance/summary";
  return apiFetch<ProvenanceSummary>(path);
}

// ---------------------------------------------------------------------------
// Write operations
// ---------------------------------------------------------------------------

export function createTopic(data: {
  name: string;
  description: string;
  domain_id?: number;
  target_venue?: string;
  deadline?: string;
}): Promise<Topic> {
  return apiFetch<Topic>("/api/topics", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateTopic(
  topicId: number,
  data: {
    name?: string;
    description?: string;
    // `null` → unassign; omit → leave untouched
    domain_id?: number | null;
    target_venue?: string;
    deadline?: string;
    status?: string;
  }
): Promise<Topic> {
  return apiFetch<Topic>(`/api/topics/${topicId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function searchPapers(data: {
  query: string;
  topic_id?: number;
  max_results?: number;
  stage?: string;
  trigger_reason?: string;
}): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>("/api/papers/search", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function ingestPaper(data: {
  source: string;
  topic_id: number;
  relevance?: string;
}): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>("/api/papers/ingest", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface StageActionResponse {
  status: string;
  summary: string;
  output: unknown;
  next_actions: string[];
  artifacts: unknown[];
  recovery_hint: string | null;
}

export function advanceTopic(
  topicId: number,
  params?: { actor?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/advance`, {
    method: "POST",
    body: JSON.stringify({ actor: params?.actor ?? "web_ui" }),
  });
}

export function checkTopicGate(topicId: number): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/gate`);
}

export function detectGaps(
  topicId: number,
  params?: { focus?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/gaps`, {
    method: "POST",
    body: JSON.stringify({ focus: params?.focus }),
  });
}

export function rankDirections(
  topicId: number,
  params?: { focus?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/directions`, {
    method: "POST",
    body: JSON.stringify({ focus: params?.focus }),
  });
}

export function extractClaims(
  topicId: number,
  params: { paper_ids: number[]; focus?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/claims`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

// ---------------------------------------------------------------------------
// Stage advancement + artifact recording
// ---------------------------------------------------------------------------

export function forceAdvanceStage(
  topicId: number,
  params?: { target_stage?: string }
): Promise<{ topic_id: number; previous_stage: string; current_stage: string }> {
  return apiFetch(`/api/topics/${topicId}/force-advance`, {
    method: "POST",
    body: JSON.stringify({ target_stage: params?.target_stage, actor: "web_ui" }),
  });
}

export function recordArtifact(
  topicId: number,
  params: { artifact_type: string; content: string; stage?: string }
): Promise<StageActionResponse> {
  return apiFetch(`/api/topics/${topicId}/artifacts`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

// ---------------------------------------------------------------------------
// Stage 1 — deeper analysis
// ---------------------------------------------------------------------------

export function identifyBaselines(
  topicId: number,
  params?: { focus?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/baselines`, {
    method: "POST",
    body: JSON.stringify({ focus: params?.focus }),
  });
}

export function buildMethodTaxonomy(
  topicId: number,
  params?: { focus?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/method-taxonomy`, {
    method: "POST",
    body: JSON.stringify({ focus: params?.focus }),
  });
}

export function buildEvidenceMatrix(
  topicId: number,
  params?: { focus?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/evidence-matrix`, {
    method: "POST",
    body: JSON.stringify({ focus: params?.focus }),
  });
}

// ---------------------------------------------------------------------------
// Stage 2 — propose
// ---------------------------------------------------------------------------

export function expandDesignBrief(
  topicId: number,
  params: { direction: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/design-brief`, {
    method: "POST",
    body: JSON.stringify({ direction: params.direction }),
  });
}

export function generateAlgorithmCandidates(
  topicId: number,
  params: { brief: Record<string, unknown>; n_candidates?: number }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/algorithm-candidates`, {
    method: "POST",
    body: JSON.stringify({
      brief: params.brief,
      n_candidates: params.n_candidates ?? 3,
    }),
  });
}

export function runCompetitiveLearning(
  topicId: number,
  params?: { venue?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/competitive-learning`, {
    method: "POST",
    body: JSON.stringify({ venue: params?.venue ?? "EMNLP" }),
  });
}

// ---------------------------------------------------------------------------
// Stage 3 — experiment
// ---------------------------------------------------------------------------

export function generateCode(
  topicId: number,
  params?: { spec?: string; focus?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/code-generate`, {
    method: "POST",
    body: JSON.stringify({ spec: params?.spec, focus: params?.focus }),
  });
}

// ---------------------------------------------------------------------------
// Stage 5 — writing quality loop
// ---------------------------------------------------------------------------

export function reviewSection(
  topicId: number,
  params: { section: string; content: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/section-review`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function reviseSection(
  topicId: number,
  params: { section: string; content: string; feedback?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/section-revise`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function checkConsistency(
  topicId: number,
  params?: { sections?: string[] }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/consistency-check`, {
    method: "POST",
    body: JSON.stringify({ sections: params?.sections }),
  });
}

export function extractWritingPattern(
  topicId: number,
  params: { paper_id: number }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/writing-pattern`, {
    method: "POST",
    body: JSON.stringify({ paper_id: params.paper_id }),
  });
}

export function buildWritingArchitecture(
  topicId: number,
  params?: { template?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/writing-architecture`, {
    method: "POST",
    body: JSON.stringify({ template: params?.template ?? "neurips" }),
  });
}

// ---------------------------------------------------------------------------
// Write stage (outline + section_draft)
// ---------------------------------------------------------------------------

export function generateOutline(
  topicId: number,
  params?: { template?: string }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/outline`, {
    method: "POST",
    body: JSON.stringify({ template: params?.template ?? "neurips" }),
  });
}

export function draftSection(
  topicId: number,
  params: { section: string; outline?: string; max_words?: number }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/section-draft`, {
    method: "POST",
    body: JSON.stringify({
      section: params.section,
      outline: params.outline,
      max_words: params.max_words ?? 0,
    }),
  });
}

// ---------------------------------------------------------------------------
// Claim verification (v2 Step 5/6)
// ---------------------------------------------------------------------------

export interface ContradictionClaim {
  id: number;
  claim_text: string;
  paper_id: number;
  modality: string;
  dataset: string;
  metric: string;
  task: string;
}

export interface Contradiction {
  id: number;
  topic_id: number;
  claim_a_id: number;
  claim_b_id: number;
  conflict_reason: string;
  status: string;
  confidence: number;
  created_at: string;
  claim_a: ContradictionClaim | null;
  claim_b: ContradictionClaim | null;
}

export function fetchContradictions(
  topicId: number
): Promise<{ topic_id: number; contradictions: Contradiction[] }> {
  return apiFetch(`/api/topics/${topicId}/contradictions`);
}

export function verifyClaims(
  topicId: number,
  params?: { pair_budget?: number; persist?: boolean }
): Promise<StageActionResponse> {
  return apiFetch<StageActionResponse>(`/api/topics/${topicId}/claim-verify`, {
    method: "POST",
    body: JSON.stringify({
      pair_budget: params?.pair_budget ?? 200,
      persist: params?.persist ?? true,
    }),
  });
}

export interface AdversarialWeakness {
  category: string;
  description: string;
  evidence: string;
  severity: "critical" | "major" | "minor";
}

export interface AdversarialReviewResult extends StageActionResponse {
  section?: string;
  weaknesses?: AdversarialWeakness[];
  critical_count?: number;
  major_count?: number;
  minor_count?: number;
  auto_opened_issue_ids?: number[];
}

// ---------------------------------------------------------------------------
// Workflow memory (v2 Step 8/9)
// ---------------------------------------------------------------------------

export interface MemoryHit {
  topic_id: number;
  topic_name: string;
  description: string;
  created_at: string;
  score: number;
  lexical_score: number;
  provenance_success_count: number;
  decision_highlights: string[];
}

export function recallSimilarRuns(body: {
  query: string;
  exclude_topic_id?: number;
  top_k?: number;
  max_age_days?: number | null;
  require_success?: boolean;
}): Promise<{ query: string; hits: MemoryHit[] }> {
  return apiFetch("/api/memory/recall", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Reports (Sprint 1 — advisor reports)
// ---------------------------------------------------------------------------

export type ReportTemplateId =
  | "abstract_only"
  | "abstract_intro"
  | "deep_pitch"
  | "full_review";

export interface ReportTemplate {
  name: string;
  sections: string[];
  description: string;
  estimated_seconds: number;
  estimated_cost_usd: number;
}

export interface ReportSummary {
  id: number;
  topic_id: number;
  template: ReportTemplateId;
  title: string;
  sections: string[];
  version_major: number;
  version_minor: number;
  has_share: boolean;
  share_token: string | null;
  share_expires_at: string | null;
  created_at: string;
  updated_at: string;
  word_count: number;
  metadata: Record<string, unknown>;
}

export interface ReportDetail extends ReportSummary {
  topic_name?: string;
  content_md: string;
  content_html: string;
}

export function fetchReportTemplates(): Promise<{
  templates: Record<ReportTemplateId, ReportTemplate>;
}> {
  return apiFetch("/api/reports/templates");
}

export function fetchTopicReports(
  topicId: number
): Promise<{ topic_id: number; reports: ReportSummary[] }> {
  return apiFetch(`/api/topics/${topicId}/reports`);
}

export function generateReport(
  topicId: number,
  body: {
    template: ReportTemplateId;
    title?: string;
    draft_missing?: boolean;
    extra_instructions?: string;
  }
): Promise<{
  id: number;
  topic_id: number;
  template: string;
  version_minor: number;
  word_count: number;
  metadata: Record<string, unknown>;
}> {
  return apiFetch(`/api/topics/${topicId}/reports`, {
    method: "POST",
    body: JSON.stringify({
      template: body.template,
      title: body.title ?? "",
      draft_missing: body.draft_missing ?? true,
      extra_instructions: body.extra_instructions ?? "",
    }),
  });
}

export interface BatchReportResult {
  template: string;
  ok: boolean;
  id?: number;
  version_minor?: number;
  word_count?: number;
  error?: string;
}

export function generateReportsBatch(
  topicId: number,
  body: {
    templates: ReportTemplateId[];
    title?: string;
    draft_missing?: boolean;
    extra_instructions?: string;
  }
): Promise<{ topic_id: number; results: BatchReportResult[] }> {
  return apiFetch(`/api/topics/${topicId}/reports:batch`, {
    method: "POST",
    body: JSON.stringify({
      templates: body.templates,
      title: body.title ?? "",
      draft_missing: body.draft_missing ?? true,
      extra_instructions: body.extra_instructions ?? "",
    }),
  });
}

export function fetchReportDetail(reportId: number): Promise<ReportDetail> {
  return apiFetch(`/api/reports/${reportId}`);
}

export function createReportShare(
  reportId: number,
  expiresInDays = 14
): Promise<{ token: string; expires_at: string | null }> {
  return apiFetch(`/api/reports/${reportId}/share`, {
    method: "POST",
    body: JSON.stringify({ expires_in_days: expiresInDays }),
  });
}

export function fetchSharedReport(token: string): Promise<ReportDetail> {
  return apiFetch(`/api/shared/reports/${token}`);
}

export function reportHtmlUrl(reportId: number): string {
  return `${API_BASE}/api/reports/${reportId}/html`;
}

export async function fetchReportHtml(reportId: number): Promise<string> {
  const res = await fetch(reportHtmlUrl(reportId));
  if (!res.ok) throw new Error(`Report HTML fetch failed: ${res.status}`);
  return res.text();
}

export function reportMarkdownUrl(reportId: number): string {
  return `${API_BASE}/api/reports/${reportId}/markdown`;
}

export function topicBibtexUrl(topicId: number): string {
  return `${API_BASE}/api/topics/${topicId}/bibtex`;
}

export async function fetchTopicBibtex(topicId: number): Promise<string> {
  const res = await fetch(topicBibtexUrl(topicId));
  if (!res.ok) throw new Error(`BibTeX export failed: ${res.status}`);
  return res.text();
}

export function adversarialReviewSection(
  topicId: number,
  params: {
    section: string;
    content: string;
    target_words?: number;
    auto_open_issues?: boolean;
  }
): Promise<AdversarialReviewResult> {
  return apiFetch<AdversarialReviewResult>(
    `/api/topics/${topicId}/adversarial-review`,
    {
      method: "POST",
      body: JSON.stringify({
        section: params.section,
        content: params.content,
        target_words: params.target_words ?? 0,
        auto_open_issues: params.auto_open_issues ?? true,
      }),
    }
  );
}

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

export function fetchAgents(params?: { status?: string }): Promise<Agent[]> {
  const sp = new URLSearchParams();
  if (params?.status) sp.set("status", params.status);
  const qs = sp.toString();
  return apiFetch<Agent[]>(`/api/agents${qs ? `?${qs}` : ""}`);
}

export interface LLMProviderInfo {
  provider: string;
  family: string;
  source: string;
  display_name?: string;
  has_key?: boolean;
  tier_suggestions?: Record<string, string>;
}

export interface LLMTierRoute {
  provider: string;
  model: string;
  source: string;
}

export interface LLMProvidersResponse {
  providers: LLMProviderInfo[];
  tier_routes: Record<string, LLMTierRoute>;
  config_loaded: boolean;
}

export function fetchLLMProviders(): Promise<LLMProvidersResponse> {
  return apiFetch<LLMProvidersResponse>("/api/llm/providers");
}

// -- LiteLLM tier suggestions & provider test ---------------------------------

export interface TierSuggestion {
  provider: string;
  model: string;
}

export interface TierSuggestionsResponse {
  available: string[];
  suggestions: Record<string, TierSuggestion>;
}

export interface ProviderTestResult {
  ok: boolean;
  response_preview?: string;
  error?: string;
}

export function fetchTierSuggestions(): Promise<TierSuggestionsResponse> {
  return apiFetch<TierSuggestionsResponse>("/api/llm/tier-suggestions");
}

export function testProvider(data: {
  provider: string;
  model: string;
  base_url?: string;
}): Promise<ProviderTestResult> {
  return apiFetch<ProviderTestResult>("/api/llm/providers/test", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function fetchAgent(agentId: number): Promise<Agent> {
  return apiFetch<Agent>(`/api/agents/${agentId}`);
}

export function createAgent(data: {
  nickname: string;
  provider: string;
  model: string;
  api_key_env: string;
  role_prefs?: Record<string, boolean>;
  monthly_budget_usd?: number;
}): Promise<Agent> {
  return apiFetch<Agent>("/api/agents", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateAgent(
  agentId: number,
  data: Partial<{
    nickname: string;
    provider: string;
    model: string;
    api_key_env: string;
    role_prefs: Record<string, boolean>;
    monthly_budget_usd: number;
    status: string;
  }>
): Promise<Agent> {
  return apiFetch<Agent>(`/api/agents/${agentId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteAgent(agentId: number): Promise<void> {
  return apiFetch(`/api/agents/${agentId}`, { method: "DELETE" });
}

export function fetchAgentPairings(params?: {
  topic_id?: number;
}): Promise<AgentPairing[]> {
  const sp = new URLSearchParams();
  if (params?.topic_id != null) sp.set("topic_id", String(params.topic_id));
  const qs = sp.toString();
  return apiFetch<AgentPairing[]>(
    `/api/agents/pairings${qs ? `?${qs}` : ""}`
  );
}

export function createAgentPairing(data: {
  name: string;
  generator_agent_id: number;
  judge_agent_id: number;
  challenger_agent_id?: number;
  topic_id?: number;
  is_global_default?: number;
}): Promise<AgentPairing> {
  return apiFetch<AgentPairing>("/api/agents/pairings", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function fetchAgentPresets(): Promise<AgentPreset[]> {
  return apiFetch<AgentPreset[]>("/api/agents/presets");
}

// ---------------------------------------------------------------------------
// User preferences
// ---------------------------------------------------------------------------

export function fetchUserPreferences(): Promise<UserPreferences> {
  return apiFetch<UserPreferences>("/api/user/preferences");
}

export function updateUserPreferences(
  data: Partial<UserPreferences>
): Promise<UserPreferences> {
  return apiFetch<UserPreferences>("/api/user/preferences", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Demo replay
// ---------------------------------------------------------------------------

export function fetchDemoEntries(): Promise<{
  entries: Array<{ key: string; stage: string; primitive: string }>;
}> {
  return apiFetch("/api/demo/replay");
}

export function demoReplay(data: {
  stage: string;
  primitive: string;
  prompt: string;
}): Promise<Record<string, unknown>> {
  return apiFetch("/api/demo/replay", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Token ledger
// ---------------------------------------------------------------------------

export function fetchLedger(params?: {
  topic_id?: number;
  agent_id?: number;
  since?: string;
  group_by?: "agent" | "stage" | "month";
}): Promise<Array<Record<string, unknown>>> {
  const sp = new URLSearchParams();
  if (params?.topic_id != null) sp.set("topic_id", String(params.topic_id));
  if (params?.agent_id != null) sp.set("agent_id", String(params.agent_id));
  if (params?.since) sp.set("since", params.since);
  if (params?.group_by) sp.set("group_by", params.group_by);
  const qs = sp.toString();
  return apiFetch(`/api/agents/ledger${qs ? `?${qs}` : ""}`);
}

export interface DailyUsage {
  day: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  calls: number;
}

export function fetchDailyUsage(params?: {
  days?: number;
  topic_id?: number;
}): Promise<DailyUsage[]> {
  const sp = new URLSearchParams();
  if (params?.days != null) sp.set("days", String(params.days));
  if (params?.topic_id != null) sp.set("topic_id", String(params.topic_id));
  const qs = sp.toString();
  return apiFetch(`/api/usage/daily${qs ? `?${qs}` : ""}`);
}

// ---------------------------------------------------------------------------
// Budgets
// ---------------------------------------------------------------------------

export interface Budget {
  id: number;
  scope: string;
  scope_id: number | null;
  monthly_cap_usd: number;
  hard_stop: number;
  created_at: string;
}

export function fetchBudgets(): Promise<Budget[]> {
  return apiFetch<Budget[]>("/api/budgets");
}

export function createBudget(data: {
  scope: string;
  scope_id?: number;
  monthly_cap_usd: number;
  hard_stop?: number;
}): Promise<Budget> {
  return apiFetch<Budget>("/api/budgets", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateBudget(
  budgetId: number,
  data: { monthly_cap_usd?: number; hard_stop?: number }
): Promise<Budget> {
  return apiFetch<Budget>(`/api/budgets/${budgetId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Venues
// ---------------------------------------------------------------------------

export interface Venue {
  id: number;
  canonical_name: string;
  aliases: string;
  ccf_rank: string | null;
  cas_zone: number | null;
  discipline: string;
}

export function fetchVenues(params?: {
  ccf_rank?: string;
  cas_zone?: number;
}): Promise<Venue[]> {
  const sp = new URLSearchParams();
  if (params?.ccf_rank) sp.set("ccf_rank", params.ccf_rank);
  if (params?.cas_zone != null) sp.set("cas_zone", String(params.cas_zone));
  const qs = sp.toString();
  return apiFetch<Venue[]>(`/api/venues${qs ? `?${qs}` : ""}`);
}

// ---------------------------------------------------------------------------
// Topic autonomy + tier
// ---------------------------------------------------------------------------

export interface TopicAutonomy {
  topic_id: number;
  level: string;
  overrides: Record<string, unknown> | null;
}

export interface TopicTier {
  topic_id: number;
  quality_tier: string;
  target_venue_tier: string;
  config: {
    judge_mode: string;
    retries: number;
    rubric_dimensions: number;
    cost_estimate: string;
  };
}

export function fetchTopicAutonomy(topicId: number): Promise<TopicAutonomy> {
  return apiFetch<TopicAutonomy>(`/api/topics/${topicId}/autonomy`);
}

export function updateTopicAutonomy(
  topicId: number,
  level: string
): Promise<{ topic_id: number; level: string }> {
  return apiFetch(`/api/topics/${topicId}/autonomy`, {
    method: "PATCH",
    body: JSON.stringify({ level }),
  });
}

export function fetchTopicTier(topicId: number): Promise<TopicTier> {
  return apiFetch<TopicTier>(`/api/topics/${topicId}/tier`);
}

export function updateTopicTier(
  topicId: number,
  tier: string
): Promise<{ topic_id: number; quality_tier: string }> {
  return apiFetch(`/api/topics/${topicId}/tier`, {
    method: "PATCH",
    body: JSON.stringify({ tier }),
  });
}

// ---------------------------------------------------------------------------
// Rollback
// ---------------------------------------------------------------------------

export interface RollbackResult {
  success: boolean;
  from_stage?: string;
  to_stage?: string;
  snapshot_id?: number;
  error?: string;
}

export interface RollbackLogEntry {
  id: number;
  topic_id: number;
  from_stage: string;
  to_stage: string;
  trigger: string;
  reason: string;
  created_at: string;
}

export function rollbackTopic(
  topicId: number,
  toStage: string,
  reason: string
): Promise<RollbackResult> {
  return apiFetch<RollbackResult>(`/api/topics/${topicId}/rollback`, {
    method: "POST",
    body: JSON.stringify({ to_stage: toStage, reason }),
  });
}

export function fetchRollbackLog(
  topicId: number
): Promise<RollbackLogEntry[]> {
  return apiFetch<RollbackLogEntry[]>(
    `/api/topics/${topicId}/rollback/log`
  );
}

// ---------------------------------------------------------------------------
// Rubric scores
// ---------------------------------------------------------------------------

export interface RubricScore {
  id: number;
  topic_id: number;
  artifact_id: number;
  stage: string;
  tier: string;
  dimension_scores: Record<string, number>;
  weighted_total: number;
  verdict: string;
  shadow_verdict: string | null;
  critique: Record<string, string>;
  rubric_version: string;
  scored_at: string;
}

export function fetchRubricScores(
  topicId: number,
  stage?: string
): Promise<RubricScore[]> {
  const sp = new URLSearchParams();
  if (stage) sp.set("stage", stage);
  const qs = sp.toString();
  return apiFetch<RubricScore[]>(
    `/api/topics/${topicId}/rubric-scores${qs ? `?${qs}` : ""}`
  );
}

// ---------------------------------------------------------------------------
// Domain suggest + topic candidates
// ---------------------------------------------------------------------------

export interface DomainSuggestion {
  suggestion: {
    name: string;
    description: string;
    keywords: string[];
  };
  source: string;
}

export function suggestDomain(idea: string): Promise<DomainSuggestion> {
  return apiFetch<DomainSuggestion>("/api/domains/suggest", {
    method: "POST",
    body: JSON.stringify({ idea }),
  });
}

export interface TopicCandidate {
  name: string;
  description: string;
  rationale: string;
}

export interface JobResult {
  id: number;
  job_type: string;
  status: string;
  result: { candidates?: TopicCandidate[] } | null;
}

export function createTopicCandidatesJob(
  domainId: number,
  tier?: string
): Promise<{ job_id: number; status: string }> {
  return apiFetch(`/api/domains/${domainId}/topic-candidates`, {
    method: "POST",
    body: JSON.stringify({ tier: tier ?? "standard" }),
  });
}

export function fetchJob(jobId: number): Promise<JobResult> {
  return apiFetch<JobResult>(`/api/jobs/${jobId}`);
}

// ---------------------------------------------------------------------------
// Domain trends
// ---------------------------------------------------------------------------

export interface TrendEntry {
  name: string;
  description: string;
  velocity_yoy: number;
  citation_median: number;
  top_venues: string[];
  publishability_score: number;
  why: string;
  seed_papers: Array<{ id: number; title: string; year: number }>;
}

export type DiscoverSignalType =
  | "paper"
  | "blog"
  | "product"
  | "repo"
  | "model"
  | "benchmark"
  | "news";

export type DiscoverSignalImportance = "act_now" | "watch" | "horizon";

export interface DiscoverSignal {
  type: DiscoverSignalType;
  title: string;
  url: string;
  published_at: string;
  importance: DiscoverSignalImportance;
  reason: string;
}

export interface DiscoverOpportunityBrief {
  title: string;
  summary: string;
  why_now: string;
  signals: DiscoverSignal[];
  trend_context: {
    window: "24h" | "7d" | "1y" | "3y" | "5y";
    growth_summary: string;
    saturation: "low" | "medium" | "high";
  };
  seed_papers: Array<{
    title: string;
    doi: string | null;
    arxiv_id: string | null;
    url: string;
    year: number | null;
  }>;
  fit_score: {
    trend: number;
    novelty: number;
    feasibility: number;
    user_fit: number;
    risk: number;
  };
  goal_previews: Array<{
    id: string;
    title: string;
    dataset: string | null;
    baseline: string | null;
    metric_name: string | null;
    target_metric_delta: number | null;
    time_window_days: number | null;
    compute_need: "low" | "medium" | "high";
    feasibility: number;
    evidence_strength: number;
    risk: number;
    first_steps: string[];
    goalability: number;
  }>;
  readiness: {
    evidence: number;
    novelty: number;
    feasibility: number;
    goalability: number;
    handoff_readiness: number;
  };
  risks: string[];
  recommended_next_steps: string[];
  rh_handoff: {
    topic_name: string;
    initial_queries: string[];
    suggested_primitives: string[];
  };
}

export interface DiscoverOpportunityCard extends DiscoverOpportunityBrief {
  slug: string;
}

export interface DiscoverOpportunitiesResponse {
  issue_id: string;
  cadence: "daily" | "weekly" | "special" | string;
  generated_at: string;
  opportunities: DiscoverOpportunityCard[];
}

export interface DiscoverOpportunityDetailResponse {
  issue_id: string;
  slug: string;
  brief: DiscoverOpportunityBrief;
}

export interface DiscoverHandoffResponse {
  topic_id: number;
  topic_name: string;
  created: boolean;
  seed_queries: string[];
  goal_seeds: DiscoverOpportunityBrief["goal_previews"];
  next_url: string;
}

export interface DiscoverWeeklyReport {
  issue_id: string;
  cadence: "daily" | "weekly" | "special" | string;
  status: "draft" | "published" | "archived" | string;
  product: "RH Discover" | string;
  title: string;
  subtitle: string;
  generated_at: string;
  brief_count: number;
  briefs: DiscoverOpportunityBrief[];
}

export interface DiscoverIssueSummary {
  issue_id: string;
  title: string;
  subtitle: string;
  generated_at: string;
  cadence: "daily" | "weekly" | "special" | string;
  status: "draft" | "published" | "archived" | string;
  brief_count: number;
}

export interface DiscoverSourceDefinition {
  id: string;
  name: string;
  family: "papers" | "blogs" | "product" | "repos_models" | "social";
  region: "global" | "cn";
  usage: "connector" | "sidecar" | "manual";
  url: string;
  signal_types: string[];
  note: string;
}

export function fetchDiscoverWeekly(params?: {
  sample?: boolean;
  generated_at?: string;
}): Promise<DiscoverWeeklyReport> {
  const sp = new URLSearchParams();
  if (params?.sample != null) sp.set("sample", String(params.sample));
  if (params?.generated_at) sp.set("generated_at", params.generated_at);
  const qs = sp.toString();
  return apiFetch<DiscoverWeeklyReport>(
    `/api/discover/weekly${qs ? `?${qs}` : ""}`
  );
}

export function fetchDiscoverIssues(params?: {
  cadence?: DiscoverIssueSummary["cadence"];
  include_drafts?: boolean;
}): Promise<DiscoverIssueSummary[]> {
  const sp = new URLSearchParams();
  if (params?.cadence) sp.set("cadence", params.cadence);
  if (params?.include_drafts != null)
    sp.set("include_drafts", String(params.include_drafts));
  const qs = sp.toString();
  return apiFetch<DiscoverIssueSummary[]>(
    `/api/discover/issues${qs ? `?${qs}` : ""}`
  );
}

export function fetchDiscoverIssue(
  issueId: string,
  params?: {
    cadence?: DiscoverIssueSummary["cadence"];
    include_drafts?: boolean;
  }
): Promise<DiscoverWeeklyReport> {
  const sp = new URLSearchParams();
  if (params?.cadence) sp.set("cadence", params.cadence);
  if (params?.include_drafts != null)
    sp.set("include_drafts", String(params.include_drafts));
  const qs = sp.toString();
  return apiFetch<DiscoverWeeklyReport>(
    `/api/discover/issues/${encodeURIComponent(issueId)}${qs ? `?${qs}` : ""}`
  );
}

export function fetchDiscoverSources(params?: {
  family?: DiscoverSourceDefinition["family"];
}): Promise<DiscoverSourceDefinition[]> {
  const sp = new URLSearchParams();
  if (params?.family) sp.set("family", params.family);
  const qs = sp.toString();
  return apiFetch<DiscoverSourceDefinition[]>(
    `/api/discover/sources${qs ? `?${qs}` : ""}`
  );
}

export function fetchDiscoverOpportunities(params?: {
  sample?: boolean;
  cadence?: DiscoverIssueSummary["cadence"];
}): Promise<DiscoverOpportunitiesResponse> {
  const sp = new URLSearchParams();
  if (params?.sample != null) sp.set("sample", String(params.sample));
  if (params?.cadence) sp.set("cadence", params.cadence);
  const qs = sp.toString();
  return apiFetch<DiscoverOpportunitiesResponse>(
    `/api/discover/opportunities${qs ? `?${qs}` : ""}`
  );
}

export function fetchDiscoverOpportunity(
  slug: string,
  params?: {
    sample?: boolean;
    cadence?: DiscoverIssueSummary["cadence"];
  }
): Promise<DiscoverOpportunityDetailResponse> {
  const sp = new URLSearchParams();
  if (params?.sample != null) sp.set("sample", String(params.sample));
  if (params?.cadence) sp.set("cadence", params.cadence);
  const qs = sp.toString();
  return apiFetch<DiscoverOpportunityDetailResponse>(
    `/api/discover/opportunities/${encodeURIComponent(slug)}${qs ? `?${qs}` : ""}`
  );
}

export function handoffDiscoverOpportunity(
  slug: string,
  body: {
    user_profile?: Record<string, unknown>;
    selected_goal_preview_ids?: string[];
  },
  params?: {
    sample?: boolean;
    cadence?: DiscoverIssueSummary["cadence"];
  }
): Promise<DiscoverHandoffResponse> {
  const sp = new URLSearchParams();
  if (params?.sample != null) sp.set("sample", String(params.sample));
  if (params?.cadence) sp.set("cadence", params.cadence);
  const qs = sp.toString();
  return apiFetch<DiscoverHandoffResponse>(
    `/api/discover/opportunities/${encodeURIComponent(slug)}/handoff${qs ? `?${qs}` : ""}`,
    {
      method: "POST",
      body: JSON.stringify(body),
    }
  );
}

export function fetchDomainTrends(params?: {
  tier?: string;
  scope?: string;
  limit?: number;
}): Promise<TrendEntry[]> {
  const sp = new URLSearchParams();
  if (params?.tier) sp.set("tier", params.tier);
  if (params?.scope) sp.set("scope", params.scope);
  if (params?.limit != null) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return apiFetch<TrendEntry[]>(
    `/api/domains/trends${qs ? `?${qs}` : ""}`
  );
}

export function refreshDomainTrends(
  body: { tier?: string; scope?: string; dry_run?: boolean } = {}
): Promise<import("./types").TrendsRefreshResult> {
  return apiFetch("/api/domains/trends/refresh", {
    method: "POST",
    body: JSON.stringify({ tier: "standard", dry_run: false, ...body }),
  });
}

export interface YearlyRow {
  year: number;
  paper_count: number;
  median_citations: number;
  top_venue_count: number;
}

export function fetchTrendsYearly(params: {
  scope?: string;
  years?: number;
}): Promise<{ scope: string; years: number; rows: YearlyRow[] }> {
  const sp = new URLSearchParams();
  if (params.scope) sp.set("scope", params.scope);
  if (params.years != null) sp.set("years", String(params.years));
  const qs = sp.toString();
  return apiFetch(`/api/trends/yearly${qs ? `?${qs}` : ""}`);
}

// ---------------------------------------------------------------------------
// Rubric calibration
// ---------------------------------------------------------------------------

export function fetchCalibrations(): Promise<import("./types").Calibration[]> {
  return apiFetch("/api/calibrations");
}

export function runCalibration(
  body: { stage?: string; tier?: string; venue_tier?: string } = {}
): Promise<import("./types").CalibrationRunResult> {
  return apiFetch("/api/calibrations/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Paper expansion jobs — multi-round search/ingest/deep-read with progress
// ---------------------------------------------------------------------------

export type ExpansionJobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface ExpansionJob {
  id: number;
  topic_id: number;
  status: ExpansionJobStatus;
  retrieval_target: number;
  deep_read_target: number;
  rounds_target: number;
  current_round: number;
  papers_fetched: number;
  papers_deep_read: number;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  /** Total papers currently linked to the topic (includes pre-existing). */
  topic_paper_count?: number;
  /** How many of those are already deep-read (deep_read=1). */
  topic_deep_read_count?: number;
}

export function fetchTopicExpansion(
  topicId: number
): Promise<ExpansionJob | null> {
  return apiFetch<ExpansionJob | null>(`/api/topics/${topicId}/expansion`);
}

export function startTopicExpansion(
  topicId: number,
  body: { retrieval_target: number; deep_read_target: number; rounds: number }
): Promise<ExpansionJob> {
  return apiFetch(`/api/topics/${topicId}/expansion`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function cancelTopicExpansion(topicId: number): Promise<ExpansionJob> {
  return apiFetch(`/api/topics/${topicId}/expansion/cancel`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Intake Profile (v3)
// ---------------------------------------------------------------------------

export type Persona =
  | "p1_no_domain"
  | "p2_domain_no_topic"
  | "p3_topic_weak"
  | "p4_topic_strong";

export type VenueConstraint = "locked" | "preferred" | "open";

export type ComputeBudget = "cpu_only" | "single_gpu" | "multi_gpu" | "cluster";

export interface IntakeProfile {
  persona: Persona;
  domain_confidence: number;
  topic_confidence: number;
  venue_constraint: VenueConstraint;
  target_venue: string | null;
  compute_budget: ComputeBudget;
  time_to_deadline_days: number | null;
  seed_present: number;
  raw_notes: string | null;
}

export function fetchIntakeProfile(
  topicId: number
): Promise<IntakeProfile | null> {
  return apiFetch<IntakeProfile | null>(
    `/api/topics/${topicId}/intake-profile`
  );
}

export function setIntakeProfile(
  topicId: number,
  body: IntakeProfile
): Promise<IntakeProfile> {
  return apiFetch<IntakeProfile>(`/api/topics/${topicId}/intake-profile`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Field Brief (v3)
// ---------------------------------------------------------------------------

export interface FieldBriefDataset {
  name: string;
  size: string | null;
  license: string | null;
  gpu_req: "cpu" | "low" | "medium" | "high";
}

export interface FieldBriefBaseline {
  name: string;
  paper_id: number | null;
  metric_name: string;
  metric_value: number;
}

export interface FieldBriefChallenge {
  problem: string;
  maturity: "saturated" | "hot" | "niche";
}

export interface FieldBriefVenueOption {
  name: string;
  deadline: string | null;
  acceptance_rate: number | null;
}

export interface FieldBrief {
  datasets: FieldBriefDataset[];
  baselines: FieldBriefBaseline[];
  narrative_patterns: string[];
  open_challenges: FieldBriefChallenge[];
  compute_bands: string[];
  venue_options: FieldBriefVenueOption[];
  saturation_score: number;
}

export interface FieldBriefMeta {
  stale: boolean;
  built_at: string;
  paper_count_at_build: number;
}

export interface FieldBriefResponse {
  brief: FieldBrief;
  meta: FieldBriefMeta;
}

export function fetchFieldBrief(
  topicId: number
): Promise<FieldBriefResponse | null> {
  return apiFetch<FieldBriefResponse | null>(
    `/api/topics/${topicId}/field-brief`
  );
}

export function rebuildFieldBrief(topicId: number): Promise<FieldBrief> {
  return apiFetch<FieldBrief>(`/api/topics/${topicId}/field-brief`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Goal Pool (v3)
// ---------------------------------------------------------------------------

export interface ScoringBreakdown {
  headroom: number;
  feasibility: number;
  evidence_coverage: number;
  venue_fit: number;
  compute_fit: number;
}

export interface Goal {
  id: number;
  dataset: string;
  baseline: string;
  metric_name: string;
  baseline_metric: number;
  target_metric_delta: number;
  target_venue: string | null;
  time_window_days: number | null;
  score: number;
  scoring_breakdown: ScoringBreakdown;
  status: string;
  priority_rank: number;
}

export function fetchGoals(topicId: number): Promise<Goal[]> {
  return apiFetch<Goal[]>(`/api/topics/${topicId}/goals`);
}

export function buildGoalPool(topicId: number): Promise<Goal[]> {
  return apiFetch<Goal[]>(`/api/topics/${topicId}/goal-pool`, {
    method: "POST",
  });
}

export function updateGoal(
  topicId: number,
  goalId: number,
  body: { status?: string; priority_rank?: number }
): Promise<Goal> {
  return apiFetch<Goal>(`/api/topics/${topicId}/goals/${goalId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteGoal(topicId: number, goalId: number): Promise<void> {
  return apiFetch(`/api/topics/${topicId}/goals/${goalId}`, {
    method: "DELETE",
  });
}

// ---------------------------------------------------------------------------
// Method Atoms (v3)
// ---------------------------------------------------------------------------

export interface MethodAtom {
  id: number;
  topic_id: number;
  source_paper_id: number;
  atom_type: string;
  name: string;
  description: string;
  deps: string[];
  reported_gain: string | null;
  reuse_risk: "low" | "medium" | "high";
}

export function fetchMethodAtoms(
  topicId: number,
  atomType?: string
): Promise<MethodAtom[]> {
  const query = atomType ? `?atom_type=${atomType}` : "";
  return apiFetch<MethodAtom[]>(
    `/api/topics/${topicId}/method-atoms${query}`
  );
}

export function harvestAtoms(
  topicId: number,
  paperIds: number[]
): Promise<{ total_atoms: number; papers_processed: number; errors: unknown[] }> {
  return apiFetch(`/api/topics/${topicId}/method-atoms/harvest`, {
    method: "POST",
    body: JSON.stringify({ paper_ids: paperIds }),
  });
}

export function deleteAtom(atomId: number): Promise<void> {
  return apiFetch(`/api/method-atoms/${atomId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Retrieval Log (v3)
// ---------------------------------------------------------------------------

export interface RetrievalLogEntry {
  id: number;
  topic_id: number;
  stage: string;
  trigger_reason: string;
  query: string;
  results_count: number;
  ingested_paper_ids: number[];
  created_at: string;
}

export function fetchRetrievalLog(
  topicId: number
): Promise<RetrievalLogEntry[]> {
  return apiFetch<RetrievalLogEntry[]>(
    `/api/topics/${topicId}/retrieval-log`
  );
}

// ---------------------------------------------------------------------------
// Experiment Matrix (v3)
// ---------------------------------------------------------------------------

export interface MatrixCell {
  id: number;
  topic_id: number;
  goal_id: number;
  atom_combo: number[];
  status: string;
  proxy_metric_name: string | null;
  proxy_metric_value: number | null;
  baseline_metric: number | null;
  delta_to_sota: number | null;
}

export function fetchExperimentMatrix(topicId: number): Promise<MatrixCell[]> {
  return apiFetch<MatrixCell[]>(
    `/api/topics/${topicId}/experiment-matrix`
  );
}

export function buildExperimentMatrix(topicId: number): Promise<MatrixCell[]> {
  return apiFetch<MatrixCell[]>(
    `/api/topics/${topicId}/experiment-matrix/build`,
    { method: "POST" }
  );
}

export function runMatrixProxy(
  topicId: number,
  maxCells: number = 20
): Promise<MatrixCell[]> {
  return apiFetch<MatrixCell[]>(
    `/api/topics/${topicId}/experiment-matrix/proxy`,
    { method: "POST", body: JSON.stringify({ max_cells: maxCells }) }
  );
}

// ---------------------------------------------------------------------------
// Venue Decision + Style Kit (v3)
// ---------------------------------------------------------------------------

export interface VenueDecisionData {
  decided_venue: string;
  decision_basis: Record<string, unknown>;
  fit_risk: string[] | null;
  source_venues: string[];
}

export interface VenueStyleKitData {
  venue: string;
  avg_section_lengths: Record<string, number>;
  citation_density: number;
  hedging_terms: string[];
  source_paper_ids: number[];
  source_venues: string[];
}

export function fetchVenueDecision(
  topicId: number
): Promise<VenueDecisionData | null> {
  return apiFetch<VenueDecisionData | null>(
    `/api/topics/${topicId}/venue-decision`
  );
}

export function decideVenue(topicId: number): Promise<VenueDecisionData> {
  return apiFetch<VenueDecisionData>(
    `/api/topics/${topicId}/venue-decision`,
    { method: "POST" }
  );
}

export function fetchVenueStyleKit(
  topicId: number
): Promise<VenueStyleKitData | null> {
  return apiFetch<VenueStyleKitData | null>(
    `/api/topics/${topicId}/venue-style-kit`
  );
}

export function buildVenueStyleKit(
  topicId: number
): Promise<VenueStyleKitData> {
  return apiFetch<VenueStyleKitData>(
    `/api/topics/${topicId}/venue-style-kit`,
    { method: "POST" }
  );
}
