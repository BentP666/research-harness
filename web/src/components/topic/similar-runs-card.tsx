"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Brain, ArrowUpRight, Loader2, Info } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { recallSimilarRuns } from "@/lib/api";

interface SimilarRunsCardProps {
  name: string;
  description: string;
  /** Optional: omit this topic from results when editing an existing one. */
  excludeTopicId?: number;
}

/** Debounce so every keystroke in the wizard doesn't trigger a request. */
function useDebounced<T>(value: T, delayMs = 400): T {
  const [d, setD] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setD(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return d;
}

export function SimilarRunsCard({
  name,
  description,
  excludeTopicId,
}: SimilarRunsCardProps) {
  const raw = `${name}\n${description}`.trim();
  const query = useDebounced(raw, 500);

  const q = useQuery({
    queryKey: ["memory-recall", query, excludeTopicId],
    queryFn: () =>
      recallSimilarRuns({
        query,
        exclude_topic_id: excludeTopicId,
        top_k: 3,
        max_age_days: 90,
        require_success: true,
      }),
    enabled: query.length >= 8,
    staleTime: 30_000,
  });

  if (query.length < 8) return null;

  return (
    <Card className="border-dashed">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Brain className="size-4" />
          Similar past runs
          {q.isPending && <Loader2 className="size-3.5 animate-spin" />}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {q.isPending ? null : q.data?.hits.length ? (
          q.data.hits.map((h) => (
            <Link
              key={h.topic_id}
              href={`/topics/${h.topic_id}`}
              className="block rounded-md border bg-card p-2.5 text-xs hover:border-sky-400 hover:bg-sky-50/50 dark:hover:bg-sky-950/20 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 font-medium">
                    <span className="truncate">{h.topic_name}</span>
                    <ArrowUpRight className="size-3 shrink-0 text-muted-foreground" />
                  </div>
                  {h.description && (
                    <p className="mt-0.5 line-clamp-2 text-muted-foreground">
                      {h.description}
                    </p>
                  )}
                </div>
                <div className="shrink-0 text-right">
                  <Badge variant="secondary" className="font-mono text-[10px]">
                    {(h.score * 100).toFixed(0)}% match
                  </Badge>
                </div>
              </div>
              {h.decision_highlights.length > 0 && (
                <ul className="mt-2 space-y-0.5 border-l-2 border-sky-400 pl-2 text-[11px] text-muted-foreground">
                  {h.decision_highlights.slice(0, 2).map((dh, i) => (
                    <li key={i} className="truncate">
                      {dh}
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-1 flex gap-2 text-[10px] text-muted-foreground">
                <span>
                  {h.provenance_success_count} successful primitive run(s)
                </span>
                {h.created_at && (
                  <span className="ml-auto">
                    {new Date(h.created_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            </Link>
          ))
        ) : (
          <div className="flex items-center gap-2 rounded-md border border-dashed p-2 text-xs text-muted-foreground">
            <Info className="size-3.5" />
            No comparable past runs in the last 90 days.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
