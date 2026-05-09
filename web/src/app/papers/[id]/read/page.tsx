"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft, FileWarning } from "lucide-react";
import { fetchPaper, paperPdfUrl } from "@/lib/api";
import { PdfReader } from "@/components/pdf/pdf-reader";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function PaperReadPage({ params }: PageProps) {
  const { id } = use(params);
  const paperId = Number(id);
  const q = useQuery({
    queryKey: ["paper", paperId],
    queryFn: () => fetchPaper(paperId),
    enabled: Number.isFinite(paperId),
    staleTime: 60_000,
  });

  if (!Number.isFinite(paperId)) {
    return (
      <div className="p-6 text-sm text-red-500">
        Invalid paper id: <code>{id}</code>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background px-4">
        <div className="flex items-center gap-3 min-w-0">
          <Button
            size="sm"
            variant="ghost"
            className="h-8"
            render={<Link href={`/papers/${paperId}`} />}
          >
            <ArrowLeft className="size-3.5" />
            Back
          </Button>
          <div className="min-w-0">
            {q.isPending ? (
              <Skeleton className="h-4 w-64" />
            ) : q.data ? (
              <h1 className="truncate text-sm font-medium" title={q.data.title}>
                {q.data.title}
              </h1>
            ) : null}
          </div>
        </div>
      </header>

      <main className="flex-1 min-h-0">
        {q.isPending && (
          <div className="grid h-full place-items-center text-sm text-muted-foreground">
            Loading paper…
          </div>
        )}
        {q.isError && (
          <div className="grid h-full place-items-center p-6 text-sm text-red-500">
            Failed to load paper #{paperId}: {(q.error as Error).message}
          </div>
        )}
        {q.data && !q.data.pdf_path && (
          <div className="grid h-full place-items-center p-6">
            <div className="max-w-md text-center">
              <FileWarning className="mx-auto mb-3 size-8 text-muted-foreground" />
              <p className="mb-2 text-sm font-medium">No PDF on file</p>
              <p className="text-xs text-muted-foreground">
                This paper has metadata only. Run{" "}
                <code className="rounded bg-muted px-1">paper_acquire</code> to
                download the PDF before opening the reader.
              </p>
            </div>
          </div>
        )}
        {q.data && q.data.pdf_path && (
          <PdfReader paper={q.data} pdfUrl={paperPdfUrl(paperId)} />
        )}
      </main>
    </div>
  );
}
