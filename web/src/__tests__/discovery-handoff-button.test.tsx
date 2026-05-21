import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DiscoveryHandoffButton } from "@/components/discovery/discovery-handoff-button";
import { handoffDiscoverOpportunity } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  handoffDiscoverOpportunity: vi.fn(),
}));

const mockedHandoff = vi.mocked(handoffDiscoverOpportunity);

describe("DiscoveryHandoffButton", () => {
  it("calls the Discover handoff API with selected goal previews", async () => {
    mockedHandoff.mockResolvedValueOnce({
      topic_id: 42,
      topic_name: "agent-eval",
      created: true,
      seed_queries: ["agent evaluation"],
      goal_seeds: [],
      next_url: "/topics/42",
    });

    render(
      <DiscoveryHandoffButton
        slug="agent-eval"
        selectedGoalPreviewIds={["goal-1"]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "创建 RH Topic" }));

    await waitFor(() => {
      expect(mockedHandoff).toHaveBeenCalledWith(
        "agent-eval",
        {
          selected_goal_preview_ids: ["goal-1"],
          user_profile: { source: "discovery" },
        },
        { sample: true },
      );
    });
    expect(await screen.findByText("已创建 RH Topic #42")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开 RH Topic" })).toHaveAttribute(
      "href",
      "/topics/42",
    );
  });

  it("shows an error state when handoff fails", async () => {
    mockedHandoff.mockRejectedValueOnce(new Error("API 500: failed"));

    render(<DiscoveryHandoffButton slug="agent-eval" />);

    fireEvent.click(screen.getByRole("button", { name: "创建 RH Topic" }));

    expect(await screen.findByText(/API 500/)).toBeInTheDocument();
  });
});
