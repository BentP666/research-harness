import type { Metadata } from "next";
import { DiscoveryShell } from "@/components/discovery/discovery-shell";

export const metadata: Metadata = {
  title: "Track 追方向 — Discovery 发现",
  description:
    "面向已有 topic 或兴趣方向的研究者，持续 triage 论文、产品、benchmark 与社区信号，并决定何时进入 RH 深挖。",
};

export default function DiscoveryTrackPage() {
  return <DiscoveryShell />;
}
