import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RetrievalTriggerButton } from "@/components/topic/retrieval-trigger-button";

vi.mock("@/lib/i18n-provider", () => ({
  useT: () => ({
    t: (key: string, vars?: Record<string, string>) =>
      vars ? `${key}:${JSON.stringify(vars)}` : key,
    locale: "en",
    setLocale: vi.fn(),
  }),
}));

const searchPapersMock = vi.fn();

vi.mock("@/lib/api", () => ({
  searchPapers: (...args: unknown[]) => searchPapersMock(...args),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  searchPapersMock.mockReset();
});

describe("RetrievalTriggerButton", () => {
  it("renders trigger button with search icon", () => {
    render(
      <Wrapper>
        <RetrievalTriggerButton topicId={1} stage="analyze" />
      </Wrapper>,
    );
    const trigger = screen.getByRole("button", { name: "retrieval.trigger" });
    expect(trigger).toBeDefined();
  });

  it("opens modal with reason chips and query textarea", () => {
    render(
      <Wrapper>
        <RetrievalTriggerButton topicId={1} stage="analyze" />
      </Wrapper>,
    );
    fireEvent.click(screen.getByRole("button", { name: "retrieval.trigger" }));
    expect(screen.getByText("retrieval.modalTitle")).toBeDefined();
    expect(screen.getByText("retrieval.reasons.missing_evidence")).toBeDefined();
    expect(screen.getByText("retrieval.reasons.weak_baseline")).toBeDefined();
    expect(screen.getByText("retrieval.reasons.user_request")).toBeDefined();
    expect(screen.getByPlaceholderText("retrieval.queryPlaceholder")).toBeDefined();
  });

  it("disables Search button when query is empty", () => {
    render(
      <Wrapper>
        <RetrievalTriggerButton topicId={1} stage="analyze" />
      </Wrapper>,
    );
    fireEvent.click(screen.getByRole("button", { name: "retrieval.trigger" }));
    const searchBtn = screen.getByRole("button", { name: /retrieval\.search/ });
    expect((searchBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it("calls searchPapers with topic_id, stage, trigger_reason on submit", async () => {
    searchPapersMock.mockResolvedValueOnce({
      status: "success",
      summary: "ok",
      output: { results: [{ id: 1 }, { id: 2 }] },
    });
    render(
      <Wrapper>
        <RetrievalTriggerButton topicId={42} stage="experiment" />
      </Wrapper>,
    );
    fireEvent.click(screen.getByRole("button", { name: "retrieval.trigger" }));
    fireEvent.click(screen.getByText("retrieval.reasons.weak_baseline"));
    fireEvent.change(screen.getByPlaceholderText("retrieval.queryPlaceholder"), {
      target: { value: "transformer baselines" },
    });
    fireEvent.click(screen.getByRole("button", { name: /retrieval\.search/ }));
    await waitFor(() => {
      expect(searchPapersMock).toHaveBeenCalledWith({
        query: "transformer baselines",
        topic_id: 42,
        stage: "experiment",
        trigger_reason: "weak_baseline",
        max_results: 20,
      });
    });
  });

  it("shows error message when searchPapers rejects", async () => {
    searchPapersMock.mockRejectedValueOnce(new Error("network down"));
    render(
      <Wrapper>
        <RetrievalTriggerButton topicId={1} stage="write" />
      </Wrapper>,
    );
    fireEvent.click(screen.getByRole("button", { name: "retrieval.trigger" }));
    fireEvent.change(screen.getByPlaceholderText("retrieval.queryPlaceholder"), {
      target: { value: "test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /retrieval\.search/ }));
    await waitFor(() => {
      expect(screen.getByText("network down")).toBeDefined();
    });
  });
});
