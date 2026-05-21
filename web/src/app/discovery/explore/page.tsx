import type { Metadata } from "next";
import { DiscoveryExplore } from "@/components/discovery/discovery-explore";

export const metadata: Metadata = {
  title: "Explore 找方向 — Discovery 发现",
  description:
    "面向博一、研一和未知 topic 的研究者，从 domain 收缩到候选 topic、starter pack 与后续 RH handoff。",
};

export default function DiscoveryExplorePage() {
  return <DiscoveryExplore />;
}
