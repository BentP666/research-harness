"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { fetchTopic } from "@/lib/api";
import { useT } from "@/lib/i18n-provider";
import { ReportBuilder } from "@/components/reports/report-builder";
import { ReportLibrary } from "@/components/reports/report-library";

export default function TopicReportsPage() {
  const params = useParams();
  const topicId = Number(params.id);
  const { t } = useT();

  const topicQ = useQuery({
    queryKey: ["topic", topicId],
    queryFn: () => fetchTopic(topicId),
    enabled: !isNaN(topicId),
  });

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6 lg:p-8">
      <div className="space-y-2">
        <Link
          href={`/topics/${topicId}`}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" />
          Back to topic
        </Link>
        <h1 className="font-serif text-3xl font-medium tracking-tight">
          {t("reports.title")}
        </h1>
        {topicQ.data && (
          <p className="text-sm text-muted-foreground">
            For{" "}
            <span className="font-medium text-foreground">
              {topicQ.data.name}
            </span>
          </p>
        )}
      </div>

      <ReportBuilder topicId={topicId} />

      <div className="space-y-3">
        <h2 className="text-lg font-semibold tracking-tight">Past reports</h2>
        <ReportLibrary topicId={topicId} />
      </div>
    </div>
  );
}
