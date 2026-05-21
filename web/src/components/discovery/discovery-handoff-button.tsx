"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import { handoffDiscoverOpportunity } from "@/lib/api";

interface DiscoveryHandoffButtonProps {
  slug: string;
  selectedGoalPreviewIds?: string[];
}

export function DiscoveryHandoffButton({
  selectedGoalPreviewIds = [],
  slug,
}: DiscoveryHandoffButtonProps) {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nextUrl, setNextUrl] = useState<string | null>(null);
  const [topicId, setTopicId] = useState<number | null>(null);

  async function submitHandoff() {
    setIsPending(true);
    setError(null);
    try {
      const result = await handoffDiscoverOpportunity(
        slug,
        {
          selected_goal_preview_ids: selectedGoalPreviewIds,
          user_profile: { source: "discovery" },
        },
        { sample: true },
      );
      setTopicId(result.topic_id);
      setNextUrl(result.next_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create RH Topic");
    } finally {
      setIsPending(false);
    }
  }

  if (nextUrl && topicId != null) {
    return (
      <div className="space-y-3">
        <div className="rounded-2xl border border-emerald-300/20 bg-emerald-300/10 px-4 py-3 text-sm font-medium text-emerald-50">
          已创建 RH Topic #{topicId}
        </div>
        <Link
          href={nextUrl}
          className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-200 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-100"
        >
          打开 RH Topic
          <ArrowRight className="size-4" />
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={submitHandoff}
        disabled={isPending}
        className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-cyan-200 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-70"
      >
        {isPending ? <Loader2 className="size-4 animate-spin" /> : null}
        创建 RH Topic
        {!isPending ? <ArrowRight className="size-4" /> : null}
      </button>
      {error ? (
        <div className="rounded-2xl border border-rose-300/20 bg-rose-300/10 px-4 py-3 text-sm leading-6 text-rose-100">
          {error}
        </div>
      ) : null}
    </div>
  );
}
