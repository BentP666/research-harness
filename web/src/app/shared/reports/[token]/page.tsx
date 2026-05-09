"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Printer, ShieldCheck, AlertCircle } from "lucide-react";
import { fetchSharedReport } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Public read-only view for advisors. No sidebar, no chrome — just the
 * document and one button to print-to-PDF.
 */
export default function SharedReportPage() {
  const params = useParams();
  const token = params.token as string;

  const { data, isPending, error } = useQuery({
    queryKey: ["shared-report", token],
    queryFn: () => fetchSharedReport(token),
    retry: false,
  });

  if (isPending) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 p-8">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 py-24 text-center">
        <AlertCircle className="size-10 text-muted-foreground" />
        <h1 className="font-serif text-2xl font-semibold">
          Link unavailable
        </h1>
        <p className="text-sm text-muted-foreground">
          This share link has expired or is invalid. Ask the author for a fresh link.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 print:bg-white">
      {/* Top banner — hidden on print */}
      <div className="sticky top-0 z-10 border-b bg-white/90 px-6 py-2 shadow-sm backdrop-blur-md dark:bg-slate-900/90 print:hidden">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="size-3.5" />
            Shared from <strong className="ml-1">Atlas</strong> · read-only preview
          </div>
          <Button
            size="sm"
            onClick={() => window.print()}
            className="gap-1.5"
          >
            <Printer className="size-3.5" />
            Save as PDF
          </Button>
        </div>
      </div>

      <div className="mx-auto max-w-3xl px-8 py-12 print:px-0 print:py-4">
        <article
          className="prose prose-slate dark:prose-invert max-w-none font-serif leading-relaxed"
          dangerouslySetInnerHTML={{ __html: stripDocumentTags(data.content_html) }}
        />

        <footer className="mt-16 border-t pt-4 text-xs text-muted-foreground">
          Generated {new Date(data.created_at).toLocaleString()} · v0.
          {data.version_minor} · {data.template.replace("_", " ")}
        </footer>
      </div>
    </div>
  );
}

/** Server-side HTML wraps <body>; strip the outer <html>/<body> so we
 *  embed cleanly in our own layout. */
function stripDocumentTags(html: string): string {
  const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  return bodyMatch ? bodyMatch[1] : html;
}
