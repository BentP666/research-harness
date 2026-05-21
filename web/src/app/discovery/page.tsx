import type { Metadata } from "next";
import { DiscoveryHome } from "@/components/discovery/discovery-home";

export const metadata: Metadata = {
  title: "Discovery 发现 · 前沿问题地图",
  description:
    "发现业界与学术界共同关注的关键问题、最新解决方案、未解决 gap 与科研叙事切入点。",
};

export default function DiscoveryPage() {
  return <DiscoveryHome />;
}
