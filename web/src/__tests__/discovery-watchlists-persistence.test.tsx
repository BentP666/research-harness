import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DiscoveryWatchlists } from "@/components/discovery/discovery-watchlists";

describe("DiscoveryWatchlists persistence", () => {
  beforeEach(() => {
    if (!window.localStorage) {
      const store = new Map<string, string>();
      Object.defineProperty(window, "localStorage", {
        configurable: true,
        value: {
          clear: () => store.clear(),
          getItem: (key: string) => store.get(key) ?? null,
          removeItem: (key: string) => store.delete(key),
          setItem: (key: string, value: string) => store.set(key, value),
        },
      });
    }
    window.localStorage.clear();
  });

  it("persists selected watchlist lanes in localStorage", () => {
    render(<DiscoveryWatchlists />);

    fireEvent.click(
      screen.getByRole("button", { name: "关注 Agent Reliability Radar" }),
    );

    expect(
      screen.getByRole("button", { name: "已关注 Agent Reliability Radar" }),
    ).toBeInTheDocument();
    expect(window.localStorage.getItem("rh-discovery-watchlist-lanes")).toContain(
      "Agent Reliability Radar",
    );

    render(<DiscoveryWatchlists />);

    expect(
      screen.getAllByRole("button", { name: "已关注 Agent Reliability Radar" })
        .length,
    ).toBeGreaterThan(0);
  });
});
