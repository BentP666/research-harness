import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PersonaStep from "@/components/onboarding/persona-step";
import ConstraintsStep from "@/components/onboarding/constraints-step";

// Mock i18n — return the key itself as the translation
vi.mock("@/lib/i18n-provider", () => ({
  useT: () => ({
    t: (key: string) => key,
    locale: "en",
    setLocale: vi.fn(),
  }),
}));

describe("PersonaStep", () => {
  it("renders 4 persona cards", () => {
    render(<PersonaStep selected={null} onSelect={() => {}} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(4);
  });

  it("highlights selected persona", () => {
    render(<PersonaStep selected="p3_topic_weak" onSelect={() => {}} />);
    const buttons = screen.getAllByRole("button");
    const selected = buttons.find((b) =>
      b.className.includes("border-blue-600")
    );
    expect(selected).toBeDefined();
    expect(selected?.textContent).toContain("onboarding.persona.p3.title");
  });

  it("calls onSelect when clicking a card", () => {
    const onSelect = vi.fn();
    render(<PersonaStep selected={null} onSelect={onSelect} />);
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[0]);
    expect(onSelect).toHaveBeenCalledWith("p1_no_domain");
  });

  it("calls onSelect for p4", () => {
    const onSelect = vi.fn();
    render(<PersonaStep selected={null} onSelect={onSelect} />);
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[3]);
    expect(onSelect).toHaveBeenCalledWith("p4_topic_strong");
  });
});

describe("ConstraintsStep", () => {
  const defaultProps = {
    venueConstraint: "preferred" as const,
    targetVenue: "",
    computeBudget: "single_gpu" as const,
    deadlineDays: 90,
    onChangeVenueConstraint: vi.fn(),
    onChangeTargetVenue: vi.fn(),
    onChangeComputeBudget: vi.fn(),
    onChangeDeadlineDays: vi.fn(),
  };

  it("renders venue constraint buttons", () => {
    render(<ConstraintsStep {...defaultProps} />);
    expect(
      screen.getByText("onboarding.constraints.venue.locked")
    ).toBeDefined();
    expect(
      screen.getByText("onboarding.constraints.venue.preferred")
    ).toBeDefined();
    expect(
      screen.getByText("onboarding.constraints.venue.open")
    ).toBeDefined();
  });

  it("shows venue input when locked", () => {
    render(<ConstraintsStep {...defaultProps} venueConstraint="locked" />);
    const input = screen.getByPlaceholderText(
      "onboarding.constraints.venuePlaceholder"
    );
    expect(input).toBeDefined();
  });

  it("hides venue input when open", () => {
    render(<ConstraintsStep {...defaultProps} venueConstraint="open" />);
    const input = screen.queryByPlaceholderText(
      "onboarding.constraints.venuePlaceholder"
    );
    expect(input).toBeNull();
  });

  it("renders 4 compute budget options", () => {
    render(<ConstraintsStep {...defaultProps} />);
    expect(
      screen.getByText("onboarding.constraints.compute.cpu")
    ).toBeDefined();
    expect(
      screen.getByText("onboarding.constraints.compute.cluster")
    ).toBeDefined();
  });
});
