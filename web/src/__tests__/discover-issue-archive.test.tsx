import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiscoverIssueArchive } from "@/components/discover/discover-issue-archive";
import type { DiscoverIssueSummary } from "@/lib/api";

const ISSUES: DiscoverIssueSummary[] = [
  {
    issue_id: "2026-05-10-weekly",
    title: "RH Discover Weekly · 创刊号",
    subtitle: "把研究与技术信号转化为可以立刻推进的研究机会。",
    generated_at: "2026-05-10",
    cadence: "weekly",
    status: "published",
    brief_count: 3,
  },
];

describe("DiscoverIssueArchive", () => {
  it("renders publishable issue links", () => {
    render(<DiscoverIssueArchive issues={ISSUES} />);

    expect(screen.getByText("RH Discover issues")).toBeInTheDocument();
    expect(screen.getByText("RH Discover Weekly · 创刊号")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /RH Discover Weekly/ })).toHaveAttribute(
      "href",
      "/discover/issues/2026-05-10-weekly",
    );
    expect(screen.getByText("3 briefs")).toBeInTheDocument();
  });

  it("explains how to publish when there are no issues", () => {
    render(<DiscoverIssueArchive issues={[]} />);

    expect(screen.getByText(/docs\/discover\/issues/)).toBeInTheDocument();
    expect(screen.getByText("rh discover validate")).toBeInTheDocument();
  });
});
