import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import FieldBriefCard from "@/components/topic/field-brief-card";

vi.mock("@/lib/i18n-provider", () => ({
  useT: () => ({
    t: (key: string) => key,
    locale: "en",
    setLocale: vi.fn(),
  }),
}));

const MOCK_BRIEF = {
  brief: {
    datasets: [{ name: "apple", size: "1000", license: "MIT", gpu_req: "cpu" }],
    baselines: [{ name: "TimeLLM", paper_id: null, metric_name: "MAPE", metric_value: 15.2 }],
    narrative_patterns: ["reasoning"],
    open_challenges: [{ problem: "chaos", maturity: "niche" }],
    compute_bands: ["CPU"],
    venue_options: [{ name: "EMNLP", deadline: null, acceptance_rate: 0.25 }],
    saturation_score: 0.42,
  },
  meta: { stale: false, built_at: "2026-04-25T00:00:00", paper_count_at_build: 10 },
};

let mockFetchResult: unknown = undefined;
let mockFetchError = false;

vi.mock("@/lib/api", () => ({
  fetchFieldBrief: vi.fn(() => {
    if (mockFetchError) throw new Error("fail");
    return Promise.resolve(mockFetchResult);
  }),
  rebuildFieldBrief: vi.fn(() => Promise.resolve(MOCK_BRIEF.brief)),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  mockFetchResult = undefined;
  mockFetchError = false;
});

describe("FieldBriefCard", () => {
  it("shows empty state when no brief exists", async () => {
    mockFetchResult = null;
    render(<Wrapper><FieldBriefCard topicId={1} /></Wrapper>);
    expect(await screen.findByText("fieldBrief.empty")).toBeDefined();
    expect(screen.getByText("fieldBrief.generate")).toBeDefined();
  });

  it("shows success state with 6 tiles", async () => {
    mockFetchResult = MOCK_BRIEF;
    render(<Wrapper><FieldBriefCard topicId={1} /></Wrapper>);
    expect(await screen.findByText("DS")).toBeDefined();
    expect(screen.getByText("BL")).toBeDefined();
    expect(screen.getByText("NP")).toBeDefined();
    expect(screen.getByText("CH")).toBeDefined();
    expect(screen.getByText("CB")).toBeDefined();
    expect(screen.getByText("VO")).toBeDefined();
  });

  it("shows saturation bar with correct label", async () => {
    mockFetchResult = MOCK_BRIEF;
    render(<Wrapper><FieldBriefCard topicId={1} /></Wrapper>);
    expect(await screen.findByText(/Yellow zone/)).toBeDefined();
  });

  it("expands tile on click", async () => {
    mockFetchResult = MOCK_BRIEF;
    render(<Wrapper><FieldBriefCard topicId={1} /></Wrapper>);
    const dsButton = await screen.findByText("DS");
    fireEvent.click(dsButton.closest("button")!);
    expect(await screen.findByText("apple")).toBeDefined();
  });
});
