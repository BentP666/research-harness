import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiscoverWeeklyShowcase } from "@/components/discover/discover-weekly-showcase";
import type { DiscoverWeeklyReport } from "@/lib/api";

const REPORT: DiscoverWeeklyReport = {
  issue_id: "2026-05-10-weekly",
  cadence: "weekly",
  status: "published",
  product: "RH Discover",
  title: "RH Discover Weekly",
  subtitle: "Signals converted into research opportunities.",
  generated_at: "2026-05-10",
  brief_count: 1,
  briefs: [
    {
      title: "Evaluate agentic literature-review workflows",
      summary: "Agentic research tools are becoming practical literature-review interfaces.",
      why_now: "Stateful agents with tools and provenance create a new evaluation problem.",
      signals: [
        {
          type: "product",
          title: "Official AI lab release stream",
          url: "https://example.com/news",
          published_at: "2026-05-10",
          importance: "watch",
          reason: "Shows product pull outside pure paper search.",
        },
      ],
      trend_context: {
        window: "7d",
        growth_summary: "Qualitative momentum across tools and benchmarks.",
        saturation: "medium",
      },
      seed_papers: [],
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
    },
  ],
};

describe("DiscoverWeeklyShowcase", () => {
  it("renders real OpportunityBrief content and RH handoff", () => {
    render(<DiscoverWeeklyShowcase report={REPORT} />);

    expect(screen.getByText("RH Discover Weekly")).toBeInTheDocument();
    expect(screen.getByText("Evaluate agentic literature-review workflows")).toBeInTheDocument();
    expect(screen.getByText(/Stateful agents/)).toBeInTheDocument();
    expect(screen.getByText("agentic literature review evaluation benchmark")).toBeInTheDocument();
    expect(screen.getByText("paper_search")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Turn into RH topic/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/topics/new?source=discover"),
    );
  });

  it("shows an empty state when no report is available", () => {
    render(<DiscoverWeeklyShowcase report={null} />);

    expect(screen.getByText("No RH Discover Weekly report yet")).toBeInTheDocument();
  });
});
