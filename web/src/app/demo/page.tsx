"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  FileSearch,
  GitBranch,
  PenLine,
  Play,
  RefreshCw,
  Sparkles,
  Target,
} from "lucide-react";
import { fetchDemoEntries, demoReplay } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const DEMO_STEPS = [
  {
    stage: "01",
    title: "Frame the research workspace",
    body: "Start with a real question: budget pacing and auto-bidding under non-stationary auctions.",
    output: "Topic frame, scope, success criteria",
    icon: Sparkles,
  },
  {
    stage: "02",
    title: "Build a paper pool",
    body: "Collect and ingest candidate papers so search results become durable research state.",
    output: "Paper pool with metadata and provenance",
    icon: FileSearch,
  },
  {
    stage: "03",
    title: "Deep-read into evidence",
    body: "Convert important papers into claims, limitations, and reusable notes instead of one-off summaries.",
    output: "Claims, evidence, reproducibility notes",
    icon: BookOpen,
  },
  {
    stage: "04",
    title: "Choose a direction",
    body: "Compare gaps, objections, and feasibility before promoting a direction into an experiment brief.",
    output: "Ranked directions and adversarial review",
    icon: Target,
  },
  {
    stage: "05",
    title: "Write from recorded work",
    body: "Draft reports and paper sections from artifacts that can be traced back to papers and tool calls.",
    output: "Outline, section draft, review notes",
    icon: PenLine,
  },
];

interface ReplayResult {
  key: string;
  stage: string;
  response: string;
  tokens: Record<string, number>;
}

export default function DemoPage() {
  const [results, setResults] = useState<ReplayResult[]>([]);
  const [running, setRunning] = useState(false);

  const entriesQuery = useQuery({
    queryKey: ["demo-entries"],
    queryFn: fetchDemoEntries,
    retry: false,
  });

  async function runDemo() {
    setResults([]);
    setRunning(true);
    const entries = entriesQuery.data?.entries ?? [];

    for (const entry of entries) {
      try {
        const resp = await demoReplay({
          stage: entry.stage,
          primitive: entry.primitive,
          prompt: "demo_run",
        });
        setResults((prev) => [
          ...prev,
          {
            key: entry.key,
            stage: entry.stage,
            response: String((resp as Record<string, unknown>).response ?? ""),
            tokens:
              ((resp as Record<string, unknown>).tokens as Record<string, number>) ?? {},
          },
        ]);
      } catch {
        // Keep the product demo useful even if a single canned entry is absent.
      }
      await new Promise((r) => setTimeout(r, 220));
    }
    setRunning(false);
  }

  const replayAvailable = Boolean(entriesQuery.data?.entries?.length);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 p-4 sm:p-6 lg:p-8">
      <section className="relative overflow-hidden rounded-[2rem] border bg-white/80 p-7 shadow-sm sm:p-10 dark:bg-slate-900/65">
        <div className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-indigo-300/20 blur-3xl dark:bg-indigo-600/10" />
        <div className="relative grid gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
          <div>
            <Badge variant="outline" className="mb-5 bg-background/80 px-3 py-1">
              <Sparkles className="size-3 text-indigo-500" />
              Product demo · no keys required
            </Badge>
            <h1 className="max-w-3xl text-4xl font-semibold tracking-[-0.035em] text-slate-950 sm:text-6xl dark:text-white">
              See a research workflow become a reusable workspace.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-8 text-muted-foreground sm:text-lg">
              This demo follows an auto-bidding topic from first question to
              evidence-backed writing material. It is designed to show the
              product shape of RH — not just a list of tools.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" onClick={runDemo} disabled={running || !replayAvailable}>
                {running ? <RefreshCw className="size-4 animate-spin" /> : <Play className="size-4" />}
                {running ? "Replaying…" : "Replay canned run"}
              </Button>
              <Button size="lg" variant="outline" render={<a href="#story" />}>
                View walkthrough
                <ArrowRight className="size-4" />
              </Button>
            </div>
            {!replayAvailable && (
              <p className="mt-4 text-sm text-muted-foreground">
                Backend replay is optional. The product walkthrough below works
                without API keys or a live model.
              </p>
            )}
          </div>

          <Card className="overflow-hidden rounded-[1.75rem] bg-slate-950 text-white shadow-2xl shadow-indigo-950/20">
            <CardContent className="p-0">
              <div className="border-b border-white/10 px-5 py-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
                  Demo workspace
                </p>
                <h2 className="mt-2 text-lg font-semibold">Auto-bidding research</h2>
              </div>
              <div className="grid gap-4 p-5">
                <div className="grid grid-cols-3 gap-3">
                  <MetricDark label="papers" value="24" />
                  <MetricDark label="claims" value="58" />
                  <MetricDark label="gaps" value="6" />
                </div>
                <div className="rounded-2xl bg-white/[0.06] p-4 ring-1 ring-white/10">
                  <div className="mb-3 flex items-center justify-between text-sm">
                    <span>Current stage</span>
                    <span className="text-indigo-200">propose</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/10">
                    <div className="h-full w-[68%] rounded-full bg-gradient-to-r from-indigo-400 to-cyan-300" />
                  </div>
                  <p className="mt-4 text-sm leading-6 text-slate-300">
                    Top direction: equilibrium-aware budget pacing with robust
                    partial-observability checks.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <section id="story" className="grid gap-4 lg:grid-cols-5">
        {DEMO_STEPS.map((step) => {
          const Icon = step.icon;
          return (
            <Card key={step.stage} className="rounded-3xl bg-white/75 shadow-sm transition hover:-translate-y-1 hover:shadow-xl hover:shadow-indigo-950/[0.06] dark:bg-slate-900/65">
              <CardContent className="p-5">
                <div className="mb-5 flex items-center justify-between">
                  <div className="flex size-11 items-center justify-center rounded-2xl bg-slate-100 text-slate-900 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-white dark:ring-slate-700">
                    <Icon className="size-5" />
                  </div>
                  <span className="text-xs font-semibold text-muted-foreground">
                    {step.stage}
                  </span>
                </div>
                <h3 className="text-base font-semibold tracking-tight text-slate-950 dark:text-white">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {step.body}
                </p>
                <div className="mt-5 rounded-2xl bg-indigo-50 p-3 text-xs font-medium text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-200">
                  {step.output}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </section>

      {results.length > 0 && (
        <section className="rounded-[2rem] border bg-white/75 p-6 shadow-sm dark:bg-slate-900/65">
          <div className="mb-5 flex items-center gap-3">
            <GitBranch className="size-5 text-indigo-500" />
            <div>
              <h2 className="text-xl font-semibold tracking-tight">Canned replay results</h2>
              <p className="text-sm text-muted-foreground">
                Pre-recorded responses, zero API cost. Use this to demo the flow on a fresh machine.
              </p>
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            {results.map((r) => (
              <Card key={r.key} className="rounded-2xl">
                <CardContent className="p-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <Badge variant="secondary">{r.stage}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {(r.tokens?.prompt ?? 0) + (r.tokens?.completion ?? 0)} tokens · $0.00
                    </span>
                  </div>
                  <p className="line-clamp-4 text-sm leading-6 text-muted-foreground">
                    {r.response}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function MetricDark({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-white/[0.06] p-3 ring-1 ring-white/10">
      <p className="text-[11px] text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}
