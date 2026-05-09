"use client";

import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Globe,
  Plus,
  Sparkles,
  Check,
  TrendingUp,
  FileText,
  Compass,
} from "lucide-react";
import Link from "next/link";
import {
  fetchDomain,
  fetchTopics,
  fetchPapers,
  fetchDomainTrends,
  createTopicCandidatesJob,
  fetchJob,
  createTopic,
} from "@/lib/api";
import type { Topic, Paper } from "@/lib/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PaperDrawer } from "@/components/paper/paper-drawer";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Time helpers
// ---------------------------------------------------------------------------

function formatRelative(dateStr: string): string {
  if (!dateStr) return "--";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

// ---------------------------------------------------------------------------
// Topic card
// ---------------------------------------------------------------------------

function TopicCard({ topic }: { topic: Topic }) {
  return (
    <Link href={`/topics/${topic.id}`} className="block">
      <Card className="transition-shadow hover:ring-2 hover:ring-blue-500/20">
        <CardHeader>
          <CardTitle>{topic.name}</CardTitle>
          {topic.description && (
            <CardDescription className="truncate">
              {topic.description}
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="text-xs">
              {topic.paper_count} paper{topic.paper_count !== 1 ? "s" : ""}
            </Badge>
            <span className="text-xs text-muted-foreground">
              Created {formatRelative(topic.created_at)}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function TopicCardSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-4 w-48" />
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-3 w-24" />
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Topic candidates panel (kept; trims unused state)
// ---------------------------------------------------------------------------

function TopicCandidatesPanel({ domainId }: { domainId: number }) {
  const qc = useQueryClient();
  const [candidates, setCandidates] = useState<
    Array<{ name: string; description: string; rationale: string; selected: boolean }>
  >([]);

  const genMut = useMutation({
    mutationFn: async () => {
      const { job_id } = await createTopicCandidatesJob(domainId);
      const job = await fetchJob(job_id);
      return job.result?.candidates ?? [];
    },
    onSuccess: (cands) => {
      setCandidates(cands.map((c) => ({ ...c, selected: false })));
    },
  });

  const commitMut = useMutation({
    mutationFn: async () => {
      const selected = candidates.filter((c) => c.selected);
      for (const c of selected) {
        await createTopic({
          name: c.name,
          description: c.description,
          domain_id: domainId,
        });
      }
    },
    onSuccess: () => {
      setCandidates([]);
      qc.invalidateQueries({ queryKey: ["domain-topics", domainId] });
    },
  });

  const selectedCount = candidates.filter((c) => c.selected).length;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <Sparkles className="size-4" />
            Suggested topics
          </CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() => genMut.mutate()}
            disabled={genMut.isPending}
          >
            {genMut.isPending ? "Generating…" : "Suggest topics"}
          </Button>
        </div>
      </CardHeader>
      {candidates.length > 0 && (
        <CardContent className="space-y-3">
          {candidates.map((c, i) => (
            <label
              key={i}
              className="flex items-start gap-3 rounded-md border p-3 cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <input
                type="checkbox"
                checked={c.selected}
                onChange={() => {
                  const next = [...candidates];
                  next[i] = { ...next[i], selected: !next[i].selected };
                  setCandidates(next);
                }}
                className="mt-0.5"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{c.name}</p>
                <p className="text-xs text-muted-foreground">{c.description}</p>
              </div>
            </label>
          ))}
          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={() => commitMut.mutate()}
              disabled={selectedCount === 0 || commitMut.isPending}
            >
              <Check className="size-3" />
              {commitMut.isPending
                ? "Creating…"
                : `Create ${selectedCount} topic${selectedCount !== 1 ? "s" : ""}`}
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sticky local nav (anchor-based — does NOT unmount sections)
// ---------------------------------------------------------------------------

const SECTION_IDS = ["overview", "trends", "papers"] as const;
type SectionId = (typeof SECTION_IDS)[number];

const SECTION_META: Record<SectionId, { label: string; icon: React.ComponentType<{ className?: string }> }> = {
  overview: { label: "Overview", icon: Compass },
  trends: { label: "Trends", icon: TrendingUp },
  papers: { label: "Papers", icon: FileText },
};

function LocalNav({ activeId }: { activeId: SectionId }) {
  return (
    <nav className="sticky top-0 z-10 -mx-6 mb-6 border-b bg-background/80 px-6 py-2 backdrop-blur lg:-mx-8 lg:px-8">
      <ul className="flex gap-1 text-sm">
        {SECTION_IDS.map((id) => {
          const Icon = SECTION_META[id].icon;
          return (
            <li key={id}>
              <a
                href={`#${id}`}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                  activeId === id
                    ? "bg-foreground/10 text-foreground"
                    : "text-muted-foreground hover:bg-muted"
                )}
              >
                <Icon className="size-3.5" />
                {SECTION_META[id].label}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DomainDetailPage() {
  const params = useParams();
  const domainId = Number(params.id);

  const domainQ = useQuery({
    queryKey: ["domain", domainId],
    queryFn: () => fetchDomain(domainId),
    enabled: !isNaN(domainId),
  });

  const topicsQ = useQuery({
    queryKey: ["domain-topics", domainId],
    queryFn: () => fetchTopics({ domain_id: domainId }),
    enabled: !isNaN(domainId),
  });

  // Trends + Papers previews — small, scoped, "see more" goes to full pages.
  const trendsQ = useQuery({
    queryKey: ["domain-trends-preview", domainId],
    // Backend doesn't yet scope trends per domain (Phase C); for now, show
    // discipline-wide carousel as a teaser and link to full explorer.
    queryFn: () => fetchDomainTrends({ limit: 4 }),
    enabled: !isNaN(domainId),
  });

  const papersQ = useQuery({
    queryKey: ["domain-papers-preview", domainId],
    queryFn: () =>
      fetchPapers({ domain_id: domainId, page: 1, page_size: 8 }),
    enabled: !isNaN(domainId),
  });

  const [activeId, setActiveId] = useState<SectionId>("overview");
  const [drawerPaperId, setDrawerPaperId] = useState<number | null>(null);

  // Active-section tracking via IntersectionObserver (anchor-only nav, no JS
  // scroll hijack).
  useEffect(() => {
    const observers: IntersectionObserver[] = [];
    SECTION_IDS.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      const obs = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting) {
              setActiveId(id);
            }
          }
        },
        { rootMargin: "-100px 0px -60% 0px" }
      );
      obs.observe(el);
      observers.push(obs);
    });
    return () => observers.forEach((o) => o.disconnect());
  }, []);

  const domain = domainQ.data;
  const topics = topicsQ.data ?? [];
  const trends = trendsQ.data ?? [];
  const papers: Paper[] = papersQ.data?.items ?? [];

  return (
    <div className="space-y-6 p-6 lg:p-8">
      {/* Back link + Header */}
      <div className="space-y-4">
        <Link
          href="/research"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-3.5" />
          Research
        </Link>

        {domainQ.isPending ? (
          <div className="space-y-3">
            <Skeleton className="h-7 w-64" />
            <Skeleton className="h-4 w-96" />
          </div>
        ) : domain ? (
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex size-9 items-center justify-center rounded-lg bg-blue-600">
                <Globe className="size-5 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">
                  {domain.name}
                </h1>
                {domain.description && (
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {domain.description}
                  </p>
                )}
              </div>
            </div>
            <Button size="sm" render={<Link href="/topics/new" />}>
              <Plus className="size-4" />
              New topic
            </Button>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Domain not found.</p>
        )}
      </div>

      {domain && (
        <>
          <LocalNav activeId={activeId} />

          {/* Overview ---------------------------------------------------- */}
          <section
            id="overview"
            className="space-y-4 scroll-mt-20"
          >
            <h2 className="text-lg font-semibold tracking-tight">
              Topics ({topics.length})
            </h2>
            <TopicCandidatesPanel domainId={domainId} />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {topicsQ.isPending ? (
                <>
                  <TopicCardSkeleton />
                  <TopicCardSkeleton />
                  <TopicCardSkeleton />
                </>
              ) : topics.length > 0 ? (
                topics.map((topic) => (
                  <TopicCard key={topic.id} topic={topic} />
                ))
              ) : (
                <p className="col-span-full text-sm text-muted-foreground">
                  No topics in this domain yet — try{" "}
                  <span className="font-medium">Suggest topics</span> above to
                  bootstrap from a research idea.
                </p>
              )}
            </div>
          </section>

          {/* Trends ------------------------------------------------------ */}
          <section id="trends" className="space-y-4 scroll-mt-20">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold tracking-tight flex items-center gap-2">
                <TrendingUp className="size-4" />
                Trends
              </h2>
              <Link
                href="/research/trends"
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Open full explorer →
              </Link>
            </div>
            <p className="text-xs text-muted-foreground">
              Currently showing discipline-wide trends. Per-domain scoping
              ships in the next release.
            </p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {trendsQ.isPending ? (
                <>
                  <Skeleton className="h-24" />
                  <Skeleton className="h-24" />
                  <Skeleton className="h-24" />
                  <Skeleton className="h-24" />
                </>
              ) : trends.length > 0 ? (
                trends.slice(0, 4).map((t, i) => (
                  <Card key={i} className="p-3">
                    <p className="text-sm font-medium leading-tight line-clamp-2">
                      {t.name}
                    </p>
                    <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                      <span
                        className={cn(
                          "tabular-nums",
                          t.velocity_yoy > 0
                            ? "text-emerald-600"
                            : "text-red-500"
                        )}
                      >
                        {t.velocity_yoy > 0 ? "+" : ""}
                        {t.velocity_yoy.toFixed(0)}% YoY
                      </span>
                      <span>Score {t.publishability_score.toFixed(1)}</span>
                    </div>
                  </Card>
                ))
              ) : (
                <p className="col-span-full text-sm text-muted-foreground">
                  No trend data yet.
                </p>
              )}
            </div>
          </section>

          {/* Papers ------------------------------------------------------ */}
          <section id="papers" className="space-y-4 scroll-mt-20">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold tracking-tight flex items-center gap-2">
                <FileText className="size-4" />
                Papers ({papersQ.data?.total ?? 0})
              </h2>
              <Link
                href="/library"
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Open library →
              </Link>
            </div>
            <Card>
              <CardContent className="divide-y p-0">
                {papersQ.isPending ? (
                  <div className="space-y-2 p-4">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Skeleton key={i} className="h-5" />
                    ))}
                  </div>
                ) : papers.length > 0 ? (
                  papers.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setDrawerPaperId(p.id)}
                      className="w-full px-4 py-3 text-left hover:bg-muted/40 transition-colors"
                    >
                      <p className="text-sm font-medium leading-snug line-clamp-2">
                        {p.title || "(untitled)"}
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {p.year ?? "—"} • {p.venue || "no venue"}
                        {p.citation_count != null && (
                          <span> • {p.citation_count} cites</span>
                        )}
                      </p>
                    </button>
                  ))
                ) : (
                  <p className="p-4 text-sm text-muted-foreground">
                    No papers linked to this domain yet. Add papers from a
                    topic page (Search & ingest) — they&apos;ll show up here.
                  </p>
                )}
              </CardContent>
            </Card>
          </section>

          <PaperDrawer
            paperId={drawerPaperId}
            open={drawerPaperId != null}
            onOpenChange={(open) => {
              if (!open) setDrawerPaperId(null);
            }}
          />
        </>
      )}
    </div>
  );
}
