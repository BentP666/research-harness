"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FileText, ArrowUpRight, Search } from "lucide-react";
import {
  fetchTopics,
  fetchTopicReports,
  type ReportSummary,
  type ReportTemplateId,
} from "@/lib/api";
import { useT } from "@/lib/i18n-provider";
import { EmptyState } from "@/components/brand/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";

/**
 * Cross-topic reports hub. Shows the most recent reports across all
 * topics so users can quickly find "the thing I sent my advisor last week."
 */
const TEMPLATE_FILTER_OPTIONS: Array<{ id: "__all__" | ReportTemplateId; label: string }> = [
  { id: "__all__", label: "All" },
  { id: "abstract_only", label: "Abstract" },
  { id: "abstract_intro", label: "Abstract + Intro" },
  { id: "deep_pitch", label: "Deep Pitch" },
  { id: "full_review", label: "Full Review" },
];

export default function ReportsHubPage() {
  const { t } = useT();
  const [query, setQuery] = useState("");
  const [templateFilter, setTemplateFilter] =
    useState<"__all__" | ReportTemplateId>("__all__");
  const [onlyShared, setOnlyShared] = useState(false);

  const topicsQ = useQuery({
    queryKey: ["topics"],
    queryFn: () => fetchTopics(),
  });

  const topicIds = (topicsQ.data ?? []).map((t) => t.id);

  const allReportsQ = useQuery({
    queryKey: ["reports-all", topicIds.join(",")],
    queryFn: async () => {
      const responses = await Promise.all(
        topicIds.map((id) => fetchTopicReports(id).catch(() => null))
      );
      const rows: Array<ReportSummary & { topic_name: string }> = [];
      responses.forEach((r, idx) => {
        if (!r) return;
        const topic = topicsQ.data?.[idx];
        r.reports.forEach((report) =>
          rows.push({ ...report, topic_name: topic?.name ?? `Topic ${report.topic_id}` })
        );
      });
      rows.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
      return rows;
    },
    enabled: topicIds.length > 0,
  });

  const allRows = allReportsQ.data ?? [];
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return allRows.filter((r) => {
      if (templateFilter !== "__all__" && r.template !== templateFilter)
        return false;
      if (onlyShared && !r.has_share) return false;
      if (q) {
        const hay = `${r.topic_name} ${r.title ?? ""} ${r.template}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [allRows, query, templateFilter, onlyShared]);

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6 lg:p-8">
      <div className="space-y-1">
        <h1 className="font-serif text-3xl font-medium tracking-tight">
          {t("reports.title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("reports.subtitle")}</p>
      </div>

      {/* Filter toolbar */}
      {allRows.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("reports.searchPlaceholder") || "Search by topic or template"}
              className="pl-8 h-9"
            />
          </div>
          <select
            value={templateFilter}
            onChange={(e) =>
              setTemplateFilter(
                e.target.value as "__all__" | ReportTemplateId
              )
            }
            className="h-9 rounded-md border border-input bg-transparent px-2 text-xs"
          >
            {TEMPLATE_FILTER_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
          <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={onlyShared}
              onChange={(e) => setOnlyShared(e.target.checked)}
              className="size-3.5"
            />
            {t("reports.onlyShared") || "Shared only"}
          </label>
          <span className="text-xs text-muted-foreground">
            {filtered.length} / {allRows.length}
          </span>
        </div>
      )}

      {topicsQ.isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : allRows.length === 0 ? (
        <EmptyState
          icon="📨"
          title={t("empty.reports.title")}
          body={t("empty.reports.body")}
          primary={
            topicIds.length > 0
              ? {
                  label: "Go to a topic",
                  href: "/research",
                }
              : {
                  label: "Create first topic",
                  href: "/topics/new",
                }
          }
        />
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {t("reports.noMatches") || "No reports match the current filter."}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {filtered.map((r) => (
            <Link
              key={r.id}
              href={`/topics/${r.topic_id}/reports`}
              className="block"
            >
              <Card className="transition-colors hover:border-foreground/30">
                <CardContent className="flex items-center gap-3 p-4">
                  <div className="flex size-9 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300">
                    <FileText className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className="truncate font-medium">
                        {r.topic_name}
                      </span>
                      <Badge variant="outline" className="text-[10px] capitalize">
                        {r.template.replace("_", " ")}
                      </Badge>
                      <Badge variant="secondary" className="text-[10px]">
                        v0.{r.version_minor}
                      </Badge>
                      {r.has_share && (
                        <Badge className="bg-emerald-100 text-emerald-700 text-[10px] dark:bg-emerald-950/40 dark:text-emerald-300">
                          shared
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {r.word_count} words · updated{" "}
                      {new Date(r.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <ArrowUpRight className="size-4 shrink-0 text-muted-foreground" />
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
