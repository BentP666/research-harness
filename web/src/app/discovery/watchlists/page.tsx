import type { Metadata } from "next";
import { DiscoveryWatchlists } from "@/components/discovery/discovery-watchlists";

export const metadata: Metadata = {
  title: "Watchlists 观察列表 — Discovery 发现",
  description:
    "长期跟踪 research directions、authors、benchmarks 和产品信号的观察列表产品页。",
};

export default function DiscoveryWatchlistsPage() {
  return <DiscoveryWatchlists />;
}
