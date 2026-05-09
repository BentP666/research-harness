import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import GoalPoolCard from "@/components/topic/goal-pool-card";

vi.mock("@/lib/i18n-provider", () => ({
  useT: () => ({
    t: (key: string) => key,
    locale: "en",
    setLocale: vi.fn(),
  }),
}));

const MOCK_GOALS = [
  {
    id: 1,
    dataset: "apple_stock",
    baseline: "TimeLLM",
    metric_name: "MAPE",
    baseline_metric: 15.2,
    target_metric_delta: 5.0,
    target_venue: "EMNLP",
    time_window_days: 90,
    score: 0.84,
    scoring_breakdown: { headroom: 0.8, feasibility: 0.9, evidence_coverage: 0.7, venue_fit: 1.0, compute_fit: 1.0 },
    status: "active",
    priority_rank: 1,
  },
  {
    id: 2,
    dataset: "NYC_Taxi",
    baseline: "Chronos",
    metric_name: "MAPE",
    baseline_metric: 18.0,
    target_metric_delta: 3.0,
    target_venue: "NeurIPS",
    time_window_days: 120,
    score: 0.76,
    scoring_breakdown: { headroom: 0.6, feasibility: 0.8, evidence_coverage: 0.6, venue_fit: 0.3, compute_fit: 1.0 },
    status: "active",
    priority_rank: 2,
  },
];

let mockGoals: unknown[] | null = null;

vi.mock("@/lib/api", () => ({
  fetchGoals: vi.fn(() => Promise.resolve(mockGoals ?? [])),
  buildGoalPool: vi.fn(() => Promise.resolve(MOCK_GOALS)),
  updateGoal: vi.fn(() => Promise.resolve(MOCK_GOALS[0])),
  deleteGoal: vi.fn(() => Promise.resolve()),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  mockGoals = null;
});

describe("GoalPoolCard", () => {
  it("shows empty state with build button", async () => {
    mockGoals = [];
    render(<Wrapper><GoalPoolCard topicId={1} /></Wrapper>);
    expect(await screen.findByText("goalPool.empty")).toBeDefined();
    expect(screen.getByText("goalPool.build")).toBeDefined();
  });

  it("shows success state with table rows", async () => {
    mockGoals = MOCK_GOALS;
    render(<Wrapper><GoalPoolCard topicId={1} /></Wrapper>);
    expect(await screen.findByText("apple_stock")).toBeDefined();
    expect(screen.getByText("NYC_Taxi")).toBeDefined();
    expect(screen.getByText("0.84")).toBeDefined();
  });

  it("shows score breakdown on hover", async () => {
    mockGoals = MOCK_GOALS;
    render(<Wrapper><GoalPoolCard topicId={1} /></Wrapper>);
    const score = await screen.findByText("0.84");
    fireEvent.mouseEnter(score.closest("td")!);
    expect(await screen.findByText("Score Breakdown")).toBeDefined();
  });

  it("highlights top-priority active goal", async () => {
    mockGoals = MOCK_GOALS;
    render(<Wrapper><GoalPoolCard topicId={1} /></Wrapper>);
    await screen.findByText("apple_stock");
    const rows = document.querySelectorAll("tr");
    const activeRow = Array.from(rows).find(r => r.className.includes("border-l-blue-600"));
    expect(activeRow).toBeDefined();
  });
});
