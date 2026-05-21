import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  usePathname: () => "/discovery",
}));

vi.mock("@/lib/api", () => ({
  fetchDiscoverOpportunities: vi.fn().mockResolvedValue({
    issue_id: "2026-05-10-weekly",
    cadence: "weekly",
    generated_at: "2026-05-10",
    opportunities: [],
  }),
}));

import { DiscoveryHome } from "@/components/discovery/discovery-home";
import { DiscoveryExplore } from "@/components/discovery/discovery-explore";
import { DiscoveryWatchlists } from "@/components/discovery/discovery-watchlists";
import { DiscoveryDigest } from "@/components/discovery/discovery-digest";

describe("Discovery product surfaces", () => {
  it("renders the discovery home as a hierarchical frontier problem map", () => {
    render(<DiscoveryHome />);

    expect(screen.getByRole("heading", { name: "前沿问题地图" })).toBeInTheDocument();
    expect(screen.getByText("10 大类")).toBeInTheDocument();
    expect(screen.getByText("2025+ 证据")).toBeInTheDocument();
    expect(screen.getByText(/每类至少 100 条 2025\+ 证据/)).toBeInTheDocument();
    expect(screen.getAllByText("Agentic Systems").length).toBeGreaterThan(0);
    expect(screen.getAllByText("AI for Research").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Robotics / Embodied AI").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/证据池 \d+/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/精选业界 \d+/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("执行边界与安全审计").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Deep Research 的证据可靠性").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Discovery 不再追新闻/)).not.toBeInTheDocument();
    expect(screen.queryByText("我还没确定 topic")).not.toBeInTheDocument();
  });

  it("renders explore as a topic-finding surface for new students", async () => {
    render(<DiscoveryExplore />);

    expect(
      screen.getByRole("heading", { name: /从大领域收缩到一个真的能做的题/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("Domain Explorer")).toBeInTheDocument();
    expect(screen.getByText("Topic Finder · 首批候选题")).toBeInTheDocument();
    expect(screen.getAllByText("Agent Security").length).toBeGreaterThan(0);
    expect(await screen.findByText("2026-05-10-weekly")).toBeInTheDocument();
  });

  it("renders watchlists as a long-term tracking surface", () => {
    render(<DiscoveryWatchlists />);

    expect(
      screen.getByRole("heading", { name: /让研究者持续知道什么值得追，什么该放弃/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("默认观察轨道")).toBeInTheDocument();
    expect(screen.getByText("Agent Reliability Radar")).toBeInTheDocument();
  });

  it("renders digest as a publishable archive surface", () => {
    render(<DiscoveryDigest />);

    expect(
      screen.getByRole("heading", { name: /Discovery 不是只给内部看，它还应该持续对外发布研究机会周报/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("RH Discover Weekly #1")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /打开 issue/ }).length).toBeGreaterThan(0);
  });
});
