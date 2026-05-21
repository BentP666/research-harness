import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { DiscoveryLiveOpportunities } from "@/components/discovery/discovery-live-opportunities";
import { fetchDiscoverOpportunities } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  fetchDiscoverOpportunities: vi.fn(),
}));

const mockedFetch = vi.mocked(fetchDiscoverOpportunities);

describe("DiscoveryLiveOpportunities", () => {
  it("loads live opportunities from the Discover API", async () => {
    mockedFetch.mockResolvedValueOnce({
      issue_id: "2026-05-10-weekly",
      cadence: "weekly",
      generated_at: "2026-05-10",
      opportunities: [
        {
          slug: "agent-eval",
          title: "Agent Evaluation",
          summary: "Evaluate agents.",
          why_now: "Production agents need evals.",
          signals: [],
          trend_context: {
            window: "7d",
            growth_summary: "Momentum.",
            saturation: "medium",
          },
          seed_papers: [],
          fit_score: {
            trend: 0.9,
            novelty: 0.8,
            feasibility: 0.7,
            user_fit: 0.8,
            risk: 0.3,
          },
          goal_previews: [
            {
              id: "goal-1",
              title: "Benchmark dynamic workflows",
              dataset: "task suite",
              baseline: "static benchmark",
              metric_name: "success",
              target_metric_delta: 0.1,
              time_window_days: 30,
              compute_need: "low",
              feasibility: 0.8,
              evidence_strength: 0.7,
              risk: 0.3,
              first_steps: ["Build tasks"],
              goalability: 1,
            },
          ],
          readiness: {
            evidence: 1,
            novelty: 0.8,
            feasibility: 0.7,
            goalability: 1,
            handoff_readiness: 1,
          },
          risks: [],
          recommended_next_steps: ["Build tasks"],
          rh_handoff: {
            topic_name: "agent-eval",
            initial_queries: ["agent eval"],
            suggested_primitives: ["paper_search"],
          },
        },
      ],
    });

    render(<DiscoveryLiveOpportunities />);

    expect(screen.getByText(/正在读取/)).toBeInTheDocument();
    expect(await screen.findByText("Agent Evaluation")).toBeInTheDocument();
    expect(screen.getByText("Benchmark dynamic workflows")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /打开 Agent Evaluation/ })).toHaveAttribute(
      "href",
      "/discovery/opportunities/agent-eval",
    );
    expect(mockedFetch).toHaveBeenCalledWith({ sample: false });
  });

  it("shows an API error state", async () => {
    mockedFetch.mockRejectedValueOnce(new Error("API unavailable"));

    render(<DiscoveryLiveOpportunities />);

    await waitFor(() => {
      expect(screen.getByText(/API unavailable/)).toBeInTheDocument();
    });
  });
});
