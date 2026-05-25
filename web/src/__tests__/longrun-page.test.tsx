import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LongRunPage from "@/app/longrun/page";

vi.mock("@/lib/i18n-provider", () => ({
  useT: () => ({
    t: (key: string) => key,
    locale: "en",
    setLocale: vi.fn(),
  }),
}));

const mockRuns = [
  {
    id: "run_1",
    title: "RFB release readiness",
    status: "waiting_gate",
    max_workers: 3,
    created_at: "2026-05-21T10:00:00Z",
    updated_at: "2026-05-21T10:10:00Z",
    task_count: 2,
    complete_count: 1,
    pending_gate_count: 1,
  },
];

const mockDetail = {
  run: {
    id: "run_1",
    title: "RFB release readiness",
    objective: "Complete release readiness",
    status: "waiting_gate",
    max_workers: 3,
    created_at: "2026-05-21T10:00:00Z",
    updated_at: "2026-05-21T10:10:00Z",
  },
  tasks: [
    {
      id: "T001",
      title: "Clean export",
      status: "complete",
      summary: "Export created and scanned.",
      dependencies: [],
      write_scope: [],
      risk_level: "low",
    },
    {
      id: "T002",
      title: "Final claim review",
      status: "queued",
      summary: "",
      dependencies: ["T001"],
      write_scope: [],
      risk_level: "medium",
    },
  ],
  gates: [
    {
      id: "G001",
      title: "Approve final review",
      gate_type: "continue_next_wave",
      status: "pending",
      token_required: true,
      notification: {
        title: "Approve final review",
        status: "pending",
        action_url:
          "http://testserver/api/longtasks/gates/G001/action?decision=approved&expires_at=1800000000&signature=signed",
        actions: {
          approve: {
            label: "Approve",
            decision: "approved",
            method: "GET",
            url: "http://testserver/api/longtasks/gates/G001/action?decision=approved&expires_at=1800000000&signature=signed",
          },
        },
      },
    },
  ],
  attempts: [],
  events: [],
};

type GateDecisionBody = {
  decision: "approved" | "rejected" | "paused" | "replan_requested";
  actor: string;
  token?: string;
  note?: string;
};

const decideLongTaskGate = vi.fn((gateId: string, body: GateDecisionBody) =>
  Promise.resolve({ accepted: Boolean(gateId && body.actor) })
);
const superviseLongTaskRun = vi.fn((runId: string) =>
  Promise.resolve({
    run_id: runId,
    cycles: 1,
    dispatched: 1,
    stop_reason: "complete",
    status: "complete",
  })
);

vi.mock("@/lib/api", () => ({
  fetchLongTaskRuns: vi.fn(() => Promise.resolve(mockRuns)),
  fetchLongTaskRun: vi.fn(() => Promise.resolve(mockDetail)),
  decideLongTaskGate: (gateId: string, body: GateDecisionBody) =>
    decideLongTaskGate(gateId, body),
  superviseLongTaskRun: (runId: string) => superviseLongTaskRun(runId),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  decideLongTaskGate.mockClear();
  superviseLongTaskRun.mockClear();
});

describe("LongRunPage", () => {
  it("shows execution path and pending mobile gate", async () => {
    render(<Wrapper><LongRunPage /></Wrapper>);

    expect(await screen.findByText("RFB release readiness")).toBeDefined();
    expect(await screen.findByText("Clean export")).toBeDefined();
    expect(screen.getByText("Final claim review")).toBeDefined();
    expect(screen.getByText("Approve final review")).toBeDefined();
    expect(screen.getByText("Export created and scanned.")).toBeDefined();
    expect(screen.getByLabelText("Signed confirmation link")).toHaveProperty(
      "value",
      expect.stringContaining("/api/longtasks/gates/G001/action")
    );
  });

  it("submits approval token from mobile gate card", async () => {
    render(<Wrapper><LongRunPage /></Wrapper>);

    await screen.findByText("Approve final review");
    fireEvent.change(screen.getByLabelText("Approval token"), {
      target: { value: "approve-me" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      expect(decideLongTaskGate).toHaveBeenCalledWith("G001", {
        decision: "approved",
        actor: "mobile-ui",
        token: "approve-me",
        note: "Approved from LongRun mobile UI",
      });
    });
  });

  it("can trigger a safe dry supervision cycle", async () => {
    render(<Wrapper><LongRunPage /></Wrapper>);

    await screen.findByText("Run safe cycle");
    fireEvent.click(screen.getByRole("button", { name: "Run safe cycle" }));

    await waitFor(() => {
      expect(superviseLongTaskRun).toHaveBeenCalledWith("run_1");
    });
  });
});
