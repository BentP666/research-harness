"use client";

import { useMemo, useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ChevronRight,
  ChevronDown,
  TrendingUp,
  RefreshCw,
  FileText,
} from "lucide-react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import {
  fetchDomainTrends,
  fetchDomains,
  fetchTopics,
  fetchTrendsYearly,
  refreshDomainTrends,
} from "@/lib/api";
import type { Domain, Topic } from "@/lib/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PaperDrawer } from "@/components/paper/paper-drawer";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Scope model
// ---------------------------------------------------------------------------

const DEFAULT_SCOPE = "discipline:cs";

interface ScopeInfo {
  kind: "discipline" | "domain" | "topic";
  value: string;
  label: string;
}

function parseScope(
  scope: string,
  domains: Domain[],
  topics: Topic[]
): ScopeInfo {
  const [kind, value] = scope.split(":", 2);
  if (kind === "domain") {
    const d = domains.find((x) => String(x.id) === value);
    return {
      kind: "domain",
      value,
      label: d ? d.name : `Domain #${value}`,
    };
  }
  if (kind === "topic") {
    const t = topics.find((x) => String(x.id) === value);
    return {
      kind: "topic",
      value,
      label: t ? t.name : `Topic #${value}`,
    };
  }
  return { kind: "discipline", value: value ?? "cs", label: "CS (all papers)" };
}

function buildBreadcrumb(
  info: ScopeInfo,
  topics: Topic[]
): Array<{ label: string; scope: string | null }> {
  const crumbs: Array<{ label: string; scope: string | null }> = [
    { label: "CS (all papers)", scope: DEFAULT_SCOPE },
  ];
  if (info.kind === "domain") {
    crumbs.push({ label: info.label, scope: null });
    return crumbs;
  }
  if (info.kind === "topic") {
    const t = topics.find((x) => String(x.id) === info.value);
    if (t?.domain_id) {
      crumbs.push({
        label: t.domain_name ?? `Domain #${t.domain_id}`,
        scope: `domain:${t.domain_id}`,
      });
    }
    crumbs.push({ label: info.label, scope: null });
    return crumbs;
  }
  return [{ label: "CS (all papers)", scope: null }];
}

// ---------------------------------------------------------------------------
// Cluster card + expanded detail (in-page accordion per codex)
// ---------------------------------------------------------------------------

interface ClusterCardProps {
  cluster: {
    name: string;
    description: string;
    publishability_score: number;
    velocity_yoy: number;
    citation_median: number;
    top_venues: string[];
    seed_papers: Array<{ id: number; title: string; year: number }>;
    why?: string;
    paper_count?: number;
    source?: "seed" | "computed";
  };
  expanded: boolean;
  onToggle: () => void;
  onPaperClick: (id: number) => void;
}

function ClusterCard({
  cluster,
  expanded,
  onToggle,
  onPaperClick,
}: ClusterCardProps) {
  const isSeed = cluster.source === "seed";

  return (
    <Card className={cn("transition-shadow", expanded && "ring-2 ring-blue-500/20")}>
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left"
        aria-expanded={expanded}
      >
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-3">
            <CardTitle className="text-sm leading-tight">{cluster.name}</CardTitle>
            <span className="text-xs font-mono tabular-nums text-muted-foreground shrink-0">
              {cluster.publishability_score.toFixed(1)}
            </span>
          </div>
          <CardDescription className="text-xs line-clamp-2">
            {cluster.description}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span
              className={cn(
                "font-mono tabular-nums font-medium",
                cluster.velocity_yoy > 0
                  ? "text-emerald-600"
                  : "text-red-500"
              )}
            >
              {cluster.velocity_yoy > 0 ? "+" : ""}
              {cluster.velocity_yoy.toFixed(0)}% YoY
            </span>
            <span className="text-muted-foreground">
              median {cluster.citation_median} cites
            </span>
            {cluster.paper_count != null && cluster.paper_count > 0 && (
              <Badge variant="outline" className="text-[10px] h-4 px-1.5">
                n={cluster.paper_count}
              </Badge>
            )}
            <Badge
              variant="outline"
              className={cn(
                "text-[10px] h-4 px-1.5 font-normal",
                isSeed
                  ? "text-amber-700 border-amber-300 dark:text-amber-400"
                  : "text-blue-700 border-blue-300 dark:text-blue-400"
              )}
              title={
                isSeed
                  ? "Editorial baseline: velocity / citation / score are hand-written estimates shipped as a starter set, not computed from your paper pool."
                  : "Computed: the cluster's numbers come from aggregating your real papers under this scope."
              }
            >
              {isSeed ? "editorial" : "computed"}
            </Badge>
          </div>
          {cluster.top_venues.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {cluster.top_venues.slice(0, 4).map((v) => (
                <Badge
                  key={v}
                  variant="secondary"
                  className="text-[10px] h-4 px-1.5"
                >
                  {v}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </button>

      {/* Expanded detail — no line chart here; the scope-level chart sits
          at the top of the page. Repeating it per-card would lie about the
          granularity (v0.3.x has no per-cluster paper mapping yet). */}
      {expanded && (
        <div className="border-t bg-muted/30 p-4 space-y-4 text-xs">
          {/* Rationale */}
          {cluster.why && (
            <div>
              <p className="mb-1 font-medium text-muted-foreground uppercase tracking-wider text-[10px]">
                Why this trend
              </p>
              <p className="leading-relaxed">{cluster.why}</p>
            </div>
          )}

          {/* Seed papers */}
          {cluster.seed_papers.length > 0 && (
            <div>
              <p className="mb-2 font-medium text-muted-foreground uppercase tracking-wider text-[10px]">
                {isSeed ? "Reference papers" : "Sample papers in this scope"}
              </p>
              <div className="space-y-1">
                {cluster.seed_papers.slice(0, 8).map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onPaperClick(p.id);
                    }}
                    className={cn(
                      "flex w-full items-start gap-2 rounded-md px-2 py-1 text-left transition-colors",
                      isSeed
                        ? "cursor-default text-muted-foreground"
                        : "hover:bg-muted/60"
                    )}
                    disabled={isSeed}
                    title={
                      isSeed
                        ? "This reference is an editorial pointer, not a paper in your library."
                        : undefined
                    }
                  >
                    <FileText className="size-3 mt-0.5 shrink-0 text-muted-foreground" />
                    <span className="truncate">
                      <span className="font-medium">{p.title}</span>
                      {p.year && (
                        <span className="text-muted-foreground"> ({p.year})</span>
                      )}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Scope-level yearly activity chart (one per page, NOT per cluster)
// ---------------------------------------------------------------------------

function YearlyActivityChart({ scope }: { scope: string }) {
  const yearlyQ = useQuery({
    queryKey: ["trends-yearly", scope],
    queryFn: () => fetchTrendsYearly({ scope, years: 5 }),
    staleTime: 60_000,
  });

  return (
    <Card>
      <CardHeader className="pb-1">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-sm">Yearly activity in this scope</CardTitle>
            <CardDescription className="text-xs">
              Paper count and median citation count per publication year.
              Computed directly from the paper pool — same curve regardless
              of which cluster you click, because v0.3.x doesn&apos;t yet map
              individual papers to specific clusters.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {yearlyQ.isPending ? (
          <Skeleton className="h-48 w-full" />
        ) : yearlyQ.data && yearlyQ.data.rows.length > 0 ? (
          <div className="h-48 w-full">
            <ResponsiveContainer>
              <LineChart
                data={yearlyQ.data.rows}
                margin={{ top: 8, right: 8, bottom: 0, left: -20 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  className="stroke-muted"
                />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fontSize: 11 }}
                />
                <Tooltip contentStyle={{ fontSize: 11, padding: "4px 8px" }} />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="paper_count"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  name="Papers"
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="median_citations"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  name="Median cites"
                  strokeDasharray="4 2"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            No papers in this scope yet — no time series to draw. Add papers
            from a topic page (Search & ingest), then come back.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Scope picker
// ---------------------------------------------------------------------------

function ScopePicker({
  currentScope,
  domains,
  topics,
  onChange,
}: {
  currentScope: string;
  domains: Domain[];
  topics: Topic[];
  onChange: (scope: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<"discipline" | "domain" | "topic">(
    (currentScope.split(":")[0] as "discipline" | "domain" | "topic") ??
      "discipline"
  );

  return (
    <div className="relative">
      <Button
        size="sm"
        variant="outline"
        onClick={() => setOpen((v) => !v)}
      >
        Change scope
        <ChevronDown className="size-3" />
      </Button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-72 rounded-md border bg-popover p-3 shadow-md">
          <div className="mb-2 flex gap-1">
            {(["discipline", "domain", "topic"] as const).map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setKind(k)}
                className={cn(
                  "rounded-md px-2.5 py-1 text-[11px] font-medium capitalize transition-colors",
                  kind === k
                    ? "bg-foreground/10 text-foreground"
                    : "text-muted-foreground hover:bg-muted"
                )}
              >
                {k}
              </button>
            ))}
          </div>
          {kind === "discipline" && (
            <button
              type="button"
              className="block w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
              onClick={() => {
                onChange(DEFAULT_SCOPE);
                setOpen(false);
              }}
            >
              CS (all papers)
            </button>
          )}
          {kind === "domain" && (
            <div className="max-h-64 overflow-y-auto">
              {domains.length === 0 ? (
                <p className="py-2 text-xs text-muted-foreground">
                  No domains defined.
                </p>
              ) : (
                domains.map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    className="block w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
                    onClick={() => {
                      onChange(`domain:${d.id}`);
                      setOpen(false);
                    }}
                  >
                    {d.name}{" "}
                    <span className="text-xs text-muted-foreground">
                      ({d.topic_count} topics)
                    </span>
                  </button>
                ))
              )}
            </div>
          )}
          {kind === "topic" && (
            <div className="max-h-64 overflow-y-auto">
              {topics.length === 0 ? (
                <p className="py-2 text-xs text-muted-foreground">
                  No topics defined.
                </p>
              ) : (
                topics.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className="block w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
                    onClick={() => {
                      onChange(`topic:${t.id}`);
                      setOpen(false);
                    }}
                  >
                    {t.name}{" "}
                    <span className="text-xs text-muted-foreground">
                      {t.domain_name && `· ${t.domain_name}`} · {t.paper_count}
                      p
                    </span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TrendsExplorerPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const scope = searchParams.get("scope") || DEFAULT_SCOPE;

  const qc = useQueryClient();
  const domainsQ = useQuery({ queryKey: ["domains"], queryFn: fetchDomains });
  const topicsQ = useQuery({
    queryKey: ["topics"],
    queryFn: () => fetchTopics(),
  });

  const trendsQ = useQuery({
    queryKey: ["trends", scope],
    queryFn: () => fetchDomainTrends({ scope, limit: 50 }),
  });

  const refreshMut = useMutation({
    mutationFn: () => refreshDomainTrends({ scope }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["trends"] });
      qc.invalidateQueries({ queryKey: ["trends-yearly"] });
      qc.invalidateQueries({ queryKey: ["domain-trends"] });
      qc.invalidateQueries({ queryKey: ["domain-trends-all"] });
    },
  });

  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [drawerPaperId, setDrawerPaperId] = useState<number | null>(null);

  const setScope = useCallback(
    (next: string) => {
      const sp = new URLSearchParams(searchParams.toString());
      if (next === DEFAULT_SCOPE) sp.delete("scope");
      else sp.set("scope", next);
      setExpandedIndex(null);
      router.replace(`/research/trends${sp.toString() ? `?${sp}` : ""}`);
    },
    [router, searchParams]
  );

  const domains = useMemo(() => domainsQ.data ?? [], [domainsQ.data]);
  const topics = useMemo(() => topicsQ.data ?? [], [topicsQ.data]);
  const trends = trendsQ.data ?? [];

  const info = useMemo(() => parseScope(scope, domains, topics), [
    scope,
    domains,
    topics,
  ]);
  const crumbs = useMemo(() => buildBreadcrumb(info, topics), [info, topics]);

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <div className="space-y-2">
        <Link
          href="/research"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-3.5" />
          Research
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
              <TrendingUp className="size-5" />
              Trends
            </h1>
            <p className="mt-0.5 text-sm text-muted-foreground max-w-2xl">
              Publishability-scored research directions. Publishability = paper
              velocity × citation median × venue quality (product with ε-floor,
              so one dead factor drags the score to zero).
            </p>
          </div>
          <div className="flex gap-2">
            <ScopePicker
              currentScope={scope}
              domains={domains}
              topics={topics}
              onChange={setScope}
            />
            <Button
              size="sm"
              variant="outline"
              onClick={() => refreshMut.mutate()}
              disabled={refreshMut.isPending}
            >
              <RefreshCw
                className={cn(
                  "size-3.5",
                  refreshMut.isPending && "animate-spin"
                )}
              />
              {refreshMut.isPending ? "Refreshing…" : "Refresh"}
            </Button>
          </div>
        </div>

        {/* Breadcrumb */}
        <nav className="flex items-center gap-1 text-xs text-muted-foreground">
          {crumbs.map((c, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <ChevronRight className="size-3" />}
              {c.scope ? (
                <button
                  type="button"
                  onClick={() => setScope(c.scope!)}
                  className="hover:text-foreground transition-colors"
                >
                  {c.label}
                </button>
              ) : (
                <span className="font-medium text-foreground">{c.label}</span>
              )}
            </span>
          ))}
        </nav>
      </div>

      {refreshMut.isError && (
        <p className="text-xs text-red-500">
          {(refreshMut.error as Error).message}
        </p>
      )}

      {/* Scope-level time-series — honest single chart, not duplicated per card */}
      <YearlyActivityChart scope={scope} />

      {/* Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {trendsQ.isPending ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="pt-4 space-y-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-8 w-full" />
              </CardContent>
            </Card>
          ))
        ) : trends.length > 0 ? (
          trends.map((t, i) => (
            <ClusterCard
              key={i}
              cluster={t}
              expanded={expandedIndex === i}
              onToggle={() =>
                setExpandedIndex((curr) => (curr === i ? null : i))
              }
              onPaperClick={(id) => setDrawerPaperId(id)}
            />
          ))
        ) : (
          <div className="col-span-full flex flex-col items-start gap-3 rounded-md border border-dashed p-6">
            <p className="text-sm text-muted-foreground">
              No trend clusters for this scope yet.
            </p>
            <Button
              size="sm"
              onClick={() => refreshMut.mutate()}
              disabled={refreshMut.isPending}
            >
              <RefreshCw
                className={cn(
                  "size-3.5",
                  refreshMut.isPending && "animate-spin"
                )}
              />
              Generate trends
            </Button>
          </div>
        )}
      </div>

      <PaperDrawer
        paperId={drawerPaperId}
        open={drawerPaperId != null}
        onOpenChange={(open) => {
          if (!open) setDrawerPaperId(null);
        }}
      />
    </div>
  );
}
