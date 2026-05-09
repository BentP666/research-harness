"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText,
  Download,
  Link as LinkIcon,
  Clock,
  Loader2,
  Copy,
  CheckCheck,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/brand/empty-state";
import {
  fetchTopicReports,
  createReportShare,
  fetchReportHtml,
  reportMarkdownUrl,
  type ReportSummary,
} from "@/lib/api";
import { useT } from "@/lib/i18n-provider";
import { cn } from "@/lib/utils";

export function ReportLibrary({ topicId }: { topicId: number }) {
  const { t } = useT();

  const { data, isPending } = useQuery({
    queryKey: ["topic-reports", topicId],
    queryFn: () => fetchTopicReports(topicId),
    refetchInterval: 20_000,
  });

  const reports = data?.reports ?? [];

  if (isPending) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="size-3.5 animate-spin" />
        {t("common.loading")}
      </div>
    );
  }

  if (reports.length === 0) {
    return (
      <EmptyState
        icon="📨"
        title={t("empty.reports.title")}
        body={t("empty.reports.body")}
      />
    );
  }

  return (
    <div className="space-y-3">
      <AnimatePresence>
        {reports.map((r, i) => (
          <motion.div
            key={r.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.25, delay: i * 0.04 }}
          >
            <ReportRow report={r} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

function ReportRow({ report }: { report: ReportSummary }) {
  const { t } = useT();
  const qc = useQueryClient();
  const [copied, setCopied] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);

  const shareMut = useMutation({
    mutationFn: () => createReportShare(report.id, 14),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["topic-reports", report.topic_id] });
      toast.success("Share link created — valid for 14 days");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const tmpl = report.template;
  const shareUrl =
    typeof window !== "undefined" && report.share_token
      ? `${window.location.origin}/shared/reports/${report.share_token}`
      : null;

  async function copyShareLink() {
    if (!shareUrl) {
      await shareMut.mutateAsync();
      return;
    }
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    toast.success("Link copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleDownloadPdf() {
    setPdfLoading(true);
    try {
      const html = await fetchReportHtml(report.id);
      const printWindow = window.open("", "_blank");
      if (!printWindow) {
        toast.error("Popup blocked — please allow popups for this site");
        return;
      }

      const title = report.title || tmpl.replace("_", " ");

      printWindow.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>${title}</title>
<style>
  @page {
    margin: 2cm 2.5cm;
    size: A4;
  }
  *, *::before, *::after { box-sizing: border-box; }
  body {
    font-family: "Georgia", "Times New Roman", serif;
    font-size: 12pt;
    line-height: 1.7;
    color: #1a1a1a;
    max-width: 100%;
    margin: 0 auto;
    padding: 1.5rem 2rem;
  }
  h1, h2, h3, h4, h5, h6 {
    font-family: "Georgia", "Times New Roman", serif;
    margin-top: 1.8em;
    margin-bottom: 0.6em;
    line-height: 1.3;
    page-break-after: avoid;
  }
  h1 { font-size: 1.6em; border-bottom: 1px solid #ccc; padding-bottom: 0.3em; }
  h2 { font-size: 1.3em; }
  h3 { font-size: 1.1em; }
  p { margin: 0 0 0.8em; orphans: 3; widows: 3; }
  blockquote {
    margin: 1em 0;
    padding: 0.5em 1em;
    border-left: 3px solid #ccc;
    color: #444;
    font-style: italic;
  }
  table { border-collapse: collapse; width: 100%; margin: 1em 0; page-break-inside: avoid; }
  th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; font-size: 0.9em; }
  th { background: #f5f5f5; font-weight: 600; }
  pre, code { font-family: "Courier New", monospace; font-size: 0.85em; }
  pre { background: #f8f8f8; padding: 0.8em 1em; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; page-break-inside: avoid; }
  img { max-width: 100%; height: auto; page-break-inside: avoid; }
  a { color: #1a1a1a; text-decoration: underline; }
  ul, ol { margin: 0.5em 0; padding-left: 1.8em; }
  li { margin-bottom: 0.3em; }
  hr { border: none; border-top: 1px solid #ddd; margin: 1.5em 0; }
  .rh-print-header {
    font-size: 0.75em;
    color: #888;
    border-bottom: 1px solid #eee;
    padding-bottom: 0.5em;
    margin-bottom: 2em;
  }
</style>
</head>
<body>
<div class="rh-print-header">
  ${title} &mdash; v${report.version_major}.${report.version_minor} &middot; ${new Date(report.updated_at).toLocaleDateString()} &middot; ${report.word_count} words
</div>
${html}
</body>
</html>`);
      printWindow.document.close();

      // Allow a brief moment for rendering before triggering print
      printWindow.addEventListener("afterprint", () => printWindow.close());
      setTimeout(() => printWindow.print(), 300);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load report");
    } finally {
      setPdfLoading(false);
    }
  }

  return (
    <Card className="overflow-hidden">
      <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300">
            <FileText className="size-4" />
          </div>
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <h4 className="truncate font-medium">{report.title || tmpl}</h4>
              <Badge variant="outline" className="text-[10px] capitalize">
                {tmpl.replace("_", " ")}
              </Badge>
              <Badge variant="secondary" className="text-[10px]">
                {t("reports.versionLabel", {
                  major: report.version_major,
                  minor: report.version_minor,
                })}
              </Badge>
              {report.has_share && (
                <Badge className="bg-emerald-100 text-emerald-700 text-[10px] dark:bg-emerald-950/40 dark:text-emerald-300">
                  shared
                </Badge>
              )}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Clock className="size-3" />
                {new Date(report.updated_at).toLocaleString()}
              </span>
              <span>{report.word_count} words</span>
              <span>{report.sections.length} sections</span>
              {report.share_expires_at && (
                <span>
                  expires{" "}
                  {new Date(report.share_expires_at).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5">
          <Button
            size="sm"
            variant="outline"
            className="gap-1"
            title={t("reports.actions.download")}
            onClick={handleDownloadPdf}
            disabled={pdfLoading}
          >
            {pdfLoading ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Download className="size-3.5" />
            )}
            {t("reports.actions.download")}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="gap-1"
            title={t("reports.actions.markdown")}
            onClick={() => window.open(reportMarkdownUrl(report.id), "_blank")}
          >
            <Download className="size-3.5" />
            .md
          </Button>
          <Button
            size="sm"
            variant={report.has_share ? "outline" : "default"}
            className={cn("gap-1", copied && "bg-emerald-600 text-white")}
            onClick={copyShareLink}
            disabled={shareMut.isPending}
          >
            {shareMut.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : copied ? (
              <CheckCheck className="size-3.5" />
            ) : report.has_share ? (
              <Copy className="size-3.5" />
            ) : (
              <LinkIcon className="size-3.5" />
            )}
            {copied
              ? "Copied"
              : report.has_share
                ? "Copy share link"
                : t("reports.actions.share")}
          </Button>
          {report.has_share && shareUrl && (
            <Button
              size="sm"
              variant="ghost"
              className="gap-1"
              onClick={() => window.open(shareUrl, "_blank")}
              title="Preview as advisor"
            >
              <ExternalLink className="size-3.5" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
