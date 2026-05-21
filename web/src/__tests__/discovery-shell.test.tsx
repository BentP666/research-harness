import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DiscoveryShell } from "@/components/discovery/discovery-shell";

describe("DiscoveryShell", () => {
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

  it("renders Discovery as a Chinese flagship intelligence workbench", () => {
    render(<DiscoveryShell />);

    expect(
      screen.getByRole("heading", { name: "AI 研究趋势情报系统" }),
    ).toBeInTheDocument();
    expect(screen.getByText("热点发现")).toBeInTheDocument();
    expect(screen.getAllByText("今日热点").length).toBeGreaterThan(0);
    expect(screen.getAllByText("本周升温").length).toBeGreaterThan(0);
    expect(screen.getAllByText("本月趋势").length).toBeGreaterThan(0);
    expect(screen.getByText("信号来源聚焦")).toBeInTheDocument();
    expect(screen.getByText("情报处理队列")).toBeInTheDocument();
    expect(screen.getByText("来源健康")).toBeInTheDocument();
    expect(screen.getByText("证据链")).toBeInTheDocument();
    expect(screen.getByText("进入指数")).toBeInTheDocument();
    expect(screen.getAllByText("黄海偏蓝").length).toBeGreaterThan(0);
  });

  it("lets users switch time windows and inspect a topic", () => {
    render(<DiscoveryShell />);

    fireEvent.click(screen.getByRole("button", { name: /本月趋势/ }));
    expect(screen.getByText("Agentic LLM Inference 系统可观测性")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("选择热点 Agentic LLM Inference 系统可观测性"));
    expect(screen.getAllByText("推理系统观测").length).toBeGreaterThan(0);
    expect(screen.getAllByText("灰海偏蓝").length).toBeGreaterThan(0);
  });

  it("links selected topics to standalone opportunity detail routes", () => {
    render(<DiscoveryShell />);

    expect(screen.getByRole("link", { name: /查看机会详情/ })).toHaveAttribute(
      "href",
      "/discovery/opportunities/security-policy-and-auditing-for-tool-using-ai-agents",
    );
    expect(screen.getByRole("link", { name: /创建 RH Topic/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/topics/new?"),
    );
  });

  it("lets users add and remove a hot topic from the watchlist", () => {
    render(<DiscoveryShell />);

    fireEvent.click(screen.getAllByRole("button", { name: "加入观察列表" })[0]);

    expect(screen.getAllByRole("button", { name: "已加入观察" }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("工具权限安全").length).toBeGreaterThan(1);

    fireEvent.click(screen.getAllByRole("button", { name: "已加入观察" })[0]);
    expect(screen.getAllByRole("button", { name: "加入观察列表" }).length).toBeGreaterThan(0);
  });

  it("filters hot topics from the header search input and supports reset", () => {
    render(<DiscoveryShell />);

    fireEvent.change(
      screen.getByRole("textbox", { name: "搜索方向、论文、repo、benchmark 或产品发布" }),
      { target: { value: "kernel" } },
    );

    expect(screen.getByText("Coding Agent 的算法发现与 Kernel 优化")).toBeInTheDocument();
    expect(screen.getByText("当前搜索：kernel")).toBeInTheDocument();

    fireEvent.change(
      screen.getByRole("textbox", { name: "搜索方向、论文、repo、benchmark 或产品发布" }),
      { target: { value: "不存在的方向" } },
    );

    expect(screen.getByText("没有匹配的热点")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "重置筛选" })[0]);
    expect(screen.getAllByText("工具权限安全").length).toBeGreaterThan(0);
  });

  it("shows active filter summary and can clear query from the filter strip", () => {
    render(<DiscoveryShell />);

    fireEvent.change(
      screen.getByRole("textbox", { name: "搜索方向、论文、repo、benchmark 或产品发布" }),
      { target: { value: "security" } },
    );

    expect(screen.getAllByText("命中 1 个热点").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /搜索：security 清空/ }));
    expect(screen.queryByText("当前搜索：security")).not.toBeInTheDocument();
  });

  it("supports mobile search input with the same filtering logic", () => {
    render(<DiscoveryShell />);

    fireEvent.change(
      screen.getByRole("textbox", { name: "移动端搜索方向、论文、repo、benchmark 或产品发布" }),
      { target: { value: "kernel" } },
    );

    expect(screen.getByText("Coding Agent 的算法发现与 Kernel 优化")).toBeInTheDocument();
    expect(screen.getByText("当前搜索：kernel")).toBeInTheDocument();
  });

  it("shows a mobile selected-topic brief with quick actions", () => {
    render(<DiscoveryShell />);

    expect(screen.getByText("当前选中热点")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /查看完整证据/ })).toHaveAttribute(
      "href",
      "#discovery-evidence-panel",
    );
    expect(screen.getByRole("link", { name: /直达建议动作/ })).toHaveAttribute(
      "href",
      "#evidence-panel-action",
    );
  });

  it("shows mobile evidence section navigation and quick action dock", () => {
    render(<DiscoveryShell />);

    expect(screen.getByRole("link", { name: "判断" })).toHaveAttribute(
      "href",
      "#evidence-panel-decision",
    );
    expect(screen.getByRole("link", { name: "证据" })).toHaveAttribute(
      "href",
      "#evidence-panel-evidence",
    );
    expect(screen.getAllByText("机会详情").length).toBeGreaterThan(0);
    expect(screen.getAllByText("创建 Topic").length).toBeGreaterThan(0);
  });
});
