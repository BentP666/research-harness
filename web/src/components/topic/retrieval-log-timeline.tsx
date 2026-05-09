"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { fetchRetrievalLog } from "@/lib/api";
import type { RetrievalLogEntry } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n-provider";

interface Props {
  topicId: number;
}

function formatRelative(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function RetrievalLogTimeline({ topicId }: Props) {
  const { t } = useT();
  const query = useQuery<RetrievalLogEntry[]>({
    queryKey: ["retrieval-log", topicId],
    queryFn: () => fetchRetrievalLog(topicId),
  });

  if (query.isLoading || query.isError) return null;
  const entries = query.data ?? [];
  if (entries.length === 0) return null;

  return (
    <Card>
      <CardContent className="p-0">
        <div className="border-b border-foreground/5 px-4 py-2 text-xs font-medium text-muted-foreground flex items-center gap-1.5">
          <Search className="size-3.5" />
          {t("retrieval.modalTitle")} · {entries.length}
        </div>
        <div className="divide-y divide-foreground/5 max-h-[300px] overflow-y-auto">
          {entries.map((entry) => (
            <div key={entry.id} className="px-4 py-2.5 space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge
                  variant="outline"
                  className="border-blue-300 bg-blue-50 text-blue-800 text-[10px] h-4 px-1.5 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-200"
                >
                  🔍 {t(`retrieval.reasons.${entry.trigger_reason}`)}
                </Badge>
                <Badge variant="secondary" className="text-[10px] h-4 px-1.5">
                  {entry.stage}
                </Badge>
                <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
                  {formatRelative(entry.created_at)}
                </span>
              </div>
              <p className="text-xs truncate" title={entry.query}>
                <span className="text-muted-foreground">Q:</span> {entry.query}
              </p>
              <div className="text-[10px] text-muted-foreground">
                {entry.results_count} results · {entry.ingested_paper_ids.length} ingested
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default RetrievalLogTimeline;
