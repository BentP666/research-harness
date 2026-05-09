"use client";

import Link from "next/link";
import {
  ExternalLink,
  FileText,
  Quote,
  Tag,
  Calendar,
  Star,
} from "lucide-react";
import { paperPdfUrl } from "@/lib/api";
import type { PaperDetail, PaperAnnotation } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const STATUS_TONE: Record<string, string> = {
  meta_only: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  pdf_ready: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  annotated:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
};

const RELEVANCE_TONE: Record<string, string> = {
  high: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
  medium: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  low: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

function arxivUrl(arxivId: string): string {
  return `https://arxiv.org/abs/${arxivId}`;
}
function doiUrl(doi: string): string {
  return doi.startsWith("http") ? doi : `https://doi.org/${doi}`;
}
function s2Url(s2Id: string): string {
  return `https://www.semanticscholar.org/paper/${s2Id}`;
}

function formatAuthors(authors: string[]): string {
  if (!authors || authors.length === 0) return "Unknown authors";
  if (authors.length <= 4) return authors.join(", ");
  return `${authors.slice(0, 3).join(", ")} et al. (+${authors.length - 3})`;
}

function annotationContentString(c: PaperAnnotation["content"]): string {
  if (typeof c === "string") return c;
  try {
    return JSON.stringify(c, null, 2);
  } catch {
    return String(c);
  }
}

interface SectionProps {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  count?: number;
  children: React.ReactNode;
}

function Section({ icon: Icon, title, count, children }: SectionProps) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Icon className="size-4 text-muted-foreground" />
        <span>{title}</span>
        {count != null && (
          <span className="text-xs font-normal text-muted-foreground">
            ({count})
          </span>
        )}
      </div>
      <div>{children}</div>
    </section>
  );
}

export function PaperDetailSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <Skeleton className="h-7 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

interface PaperDetailContentProps {
  paper: PaperDetail;
  /** When true, hide the title-bar back link / external nav (drawer mode). */
  compact?: boolean;
}

export function PaperDetailContent({
  paper,
  compact = false,
}: PaperDetailContentProps) {
  const hasPdf = !!paper.pdf_path;
  const externalLinks: { label: string; href: string }[] = [];
  if (paper.arxiv_id) externalLinks.push({ label: "arXiv", href: arxivUrl(paper.arxiv_id) });
  if (paper.doi) externalLinks.push({ label: "DOI", href: doiUrl(paper.doi) });
  if (paper.s2_id) externalLinks.push({ label: "Semantic Scholar", href: s2Url(paper.s2_id) });
  if (paper.url) externalLinks.push({ label: "Source", href: paper.url });

  return (
    <div className={cn("space-y-6", !compact && "p-6 lg:p-8")}>
      {/* Header */}
      <div className="space-y-3">
        <h1
          className={cn(
            "font-semibold tracking-tight leading-tight",
            compact ? "text-lg" : "text-2xl"
          )}
        >
          {paper.title || "(untitled)"}
        </h1>
        <p className="text-sm text-muted-foreground">
          {formatAuthors(paper.authors)}
        </p>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {paper.year && (
            <span className="inline-flex items-center gap-1 text-muted-foreground">
              <Calendar className="size-3" />
              {paper.year}
            </span>
          )}
          {paper.venue && (
            <Badge variant="secondary" className="text-xs">
              {paper.venue}
            </Badge>
          )}
          {paper.citation_count != null && (
            <span className="inline-flex items-center gap-1 text-muted-foreground">
              <Star className="size-3" />
              {paper.citation_count} cites
            </span>
          )}
          <Badge
            variant="secondary"
            className={cn(
              "text-xs font-normal",
              STATUS_TONE[paper.status] ?? STATUS_TONE.meta_only
            )}
          >
            {paper.status}
          </Badge>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant={hasPdf ? "default" : "outline"}
          disabled={!hasPdf}
          render={
            hasPdf ? (
              <a
                href={paperPdfUrl(paper.id)}
                target="_blank"
                rel="noopener noreferrer"
              />
            ) : undefined
          }
        >
          <FileText className="size-3.5" />
          {hasPdf ? "Open PDF" : "No PDF on file"}
        </Button>
        {externalLinks.map((l) => (
          <Button
            key={l.label}
            size="sm"
            variant="outline"
            render={<a href={l.href} target="_blank" rel="noopener noreferrer" />}
          >
            <ExternalLink className="size-3.5" />
            {l.label}
          </Button>
        ))}
      </div>

      {/* Abstract */}
      {paper.abstract && paper.abstract.trim() && (
        <Section icon={Quote} title="Abstract">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
            {paper.abstract}
          </p>
        </Section>
      )}

      {/* Topics */}
      <Section icon={Tag} title="Topics" count={paper.topics.length}>
        {paper.topics.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Not assigned to any topic yet.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {paper.topics.map((t) => (
              <Link
                key={t.id}
                href={`/topics/${t.id}`}
                className="group inline-flex items-center gap-2 rounded-md border border-border px-2 py-1 text-xs hover:border-foreground/30 hover:bg-muted transition-colors"
              >
                <span className="font-medium">{t.name}</span>
                {t.relevance && (
                  <Badge
                    variant="secondary"
                    className={cn(
                      "text-[10px] h-4 px-1.5 font-normal capitalize",
                      RELEVANCE_TONE[t.relevance] ?? RELEVANCE_TONE.low
                    )}
                  >
                    {t.relevance}
                  </Badge>
                )}
              </Link>
            ))}
          </div>
        )}
      </Section>

      {/* Annotations */}
      <Section
        icon={FileText}
        title="Annotations"
        count={paper.annotations.length}
      >
        {paper.annotations.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No annotations recorded yet. Annotations appear after the paper is
            run through the analysis pipeline.
          </p>
        ) : (
          <div className="space-y-3">
            {paper.annotations.map((a) => (
              <div
                key={a.id}
                className="rounded-md border border-border bg-card p-3 text-sm"
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {a.section}
                  </span>
                  {a.source && (
                    <span className="text-[10px] text-muted-foreground">
                      via {a.source}
                    </span>
                  )}
                </div>
                <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed text-foreground/90 font-sans">
                  {annotationContentString(a.content)}
                </pre>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
