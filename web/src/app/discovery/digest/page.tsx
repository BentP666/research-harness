import type { Metadata } from "next";
import { DiscoveryDigest } from "@/components/discovery/discovery-digest";

export const metadata: Metadata = {
  title: "Digest 周报归档 — Discovery 发现",
  description:
    "Discovery 的周报归档与对外发布面，展示如何把内部 triage 结果转成研究机会内容产品。",
};

export default function DiscoveryDigestPage() {
  return <DiscoveryDigest />;
}
