import { describe, expect, it } from "vitest";
import type { DiscoverWeeklyReport } from "@/lib/api";
import type { DiscoveryTopicCandidate } from "@/lib/discovery-product";
import {
  buildNewTopicHrefFromDiscoverBrief,
  buildNewTopicHrefFromTopicCandidate,
  formatDiscoverBriefDescription,
  formatTopicCandidateDescription,
  parseNewTopicPrefillSearch,
} from "@/lib/topic-prefill";

const BRIEF: DiscoverWeeklyReport["briefs"][number] = {
  title: "Evaluate agentic literature-review workflows",
  summary: "Agentic research tools are becoming practical literature-review interfaces.",
  why_now: "Stateful agents with tools and provenance create a new evaluation problem.",
  signals: [],
  trend_context: {
    window: "7d",
    growth_summary: "Qualitative momentum across tools and benchmarks.",
    saturation: "medium",
  },
  seed_papers: [
    {
      title: "A seed with DOI",
      doi: "10.1145/1234567.1234568",
      arxiv_id: null,
      url: "https://example.com/doi-paper",
      year: 2026,
    },
    {
      title: "A seed with arXiv",
      doi: null,
      arxiv_id: "2401.12345",
      url: "https://arxiv.org/abs/2401.12345",
      year: 2024,
    },
  ],
  fit_score: {
    trend: 0.75,
    novelty: 0.68,
    feasibility: 0.82,
    user_fit: 0.8,
    risk: 0.35,
  },
  goal_previews: [
    {
      id: "goal-1",
      title: "Build a traceability benchmark slice",
      dataset: "small literature-review workflow traces",
      baseline: "manual review checklist",
      metric_name: "traceability coverage",
      target_metric_delta: 0.1,
      time_window_days: 30,
      compute_need: "low",
      feasibility: 0.82,
      evidence_strength: 0.75,
      risk: 0.35,
      first_steps: ["Define trace schema"],
      goalability: 1,
    },
  ],
  readiness: {
    evidence: 1,
    novelty: 0.68,
    feasibility: 0.82,
    goalability: 1,
    handoff_readiness: 1,
  },
  risks: ["Can become a tool demo without blinded judging."],
  recommended_next_steps: ["Build a small traceability benchmark."],
  rh_handoff: {
    topic_name: "evaluate-agentic-literature-review-workflows",
    initial_queries: ["agentic literature review evaluation benchmark"],
    suggested_primitives: ["paper_search", "paper_ingest", "gap_detect"],
  },
};

const CANDIDATE: DiscoveryTopicCandidate = {
  slug: "dynamic-task-benchmark-slice",
  title: "动态信息环境下的 agent benchmark slice",
  domainSlug: "agent-evaluation",
  fitFor: ["博一/研一，还没有 topic", "想尽快起一个硕士题"],
  whyItFits: "适合先做 benchmark audit 和 failure taxonomy。",
  novelty: 78,
  feasibility: 88,
  resourceNeed: "low",
  horizon: "8-weeks",
  firstMoves: ["选职业任务子集", "定义动态扰动", "记录失败差异"],
  starterPack: {
    papers: ["OccuBench", "ClawArena"],
    skills: ["literature-search", "claim-extraction"],
    outputs: ["Task suite", "Failure taxonomy"],
  },
};

describe("RH Discover topic prefill", () => {
  it("builds a topic creation URL from an OpportunityBrief handoff", () => {
    const href = buildNewTopicHrefFromDiscoverBrief(BRIEF);
    const url = new URL(href, "http://localhost");

    expect(url.pathname).toBe("/topics/new");
    expect(url.searchParams.get("source")).toBe("discover");
    expect(url.searchParams.get("name")).toBe(
      "evaluate-agentic-literature-review-workflows",
    );
    expect(url.searchParams.get("description")).toContain("Initial RH queries");
    expect(url.searchParams.get("seed_papers")).toBe(
      "10.1145/1234567.1234568\n2401.12345",
    );
  });

  it("formats Discover context into an editable topic description", () => {
    const description = formatDiscoverBriefDescription(BRIEF);

    expect(description).toContain("Why now:");
    expect(description).toContain("Recommended next steps:");
    expect(description).toContain("Risks / watch-outs:");
  });

  it("builds a topic creation URL from an explore candidate starter pack", () => {
    const href = buildNewTopicHrefFromTopicCandidate(CANDIDATE, "Agent Evaluation");
    const url = new URL(href, "http://localhost");

    expect(url.pathname).toBe("/topics/new");
    expect(url.searchParams.get("source")).toBe("discovery_explore");
    expect(url.searchParams.get("name")).toBe(CANDIDATE.title);
    expect(url.searchParams.get("seed_papers")).toBe("OccuBench\nClawArena");
    expect(url.searchParams.get("description")).toContain("Starter papers:");
  });

  it("formats candidate context into a reusable starter description", () => {
    const description = formatTopicCandidateDescription(CANDIDATE, "Agent Evaluation");

    expect(description).toContain("Domain:");
    expect(description).toContain("First moves:");
    expect(description).toContain("Suggested RH skills:");
    expect(description).toContain("Expected first outputs:");
  });

  it("parses query params into the new topic wizard prefill shape", () => {
    const prefill = parseNewTopicPrefillSearch(
      "?source=discover&name=topic-a&description=desc&seed_papers=2401.12345%0A10.1145%2F1&target_venue=KDD%202027",
    );

    expect(prefill).toEqual({
      source: "discover",
      name: "topic-a",
      description: "desc",
      targetVenue: "KDD 2027",
      deadline: "",
      seedPapersRaw: "2401.12345\n10.1145/1",
    });
  });
});
