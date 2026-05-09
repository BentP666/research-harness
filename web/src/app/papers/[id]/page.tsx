"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { fetchPaper } from "@/lib/api";
import {
  PaperDetailContent,
  PaperDetailSkeleton,
} from "@/components/paper/paper-detail-content";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function PaperPage({ params }: PageProps) {
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
    <div className="mx-auto max-w-4xl">
      <div className="px-6 pt-6 lg:px-8">
        <Link
          href="/library"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-3.5" />
          Library
        </Link>
      </div>
      {q.isPending && <PaperDetailSkeleton />}
      {q.isError && (
        <div className="p-6 text-sm text-red-500">
          Failed to load paper #{paperId}: {(q.error as Error).message}
        </div>
      )}
      {q.data && <PaperDetailContent paper={q.data} />}
    </div>
  );
}
