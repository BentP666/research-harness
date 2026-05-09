"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Play, Info } from "lucide-react";
import { fetchDemoEntries, demoReplay } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function DemoPage() {
  const [results, setResults] = useState<Array<{ key: string; stage: string; response: string; tokens: Record<string, number> }>>([]);
  const [running, setRunning] = useState(false);

  const entriesQuery = useQuery({
    queryKey: ["demo-entries"],
    queryFn: fetchDemoEntries,
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
            tokens: ((resp as Record<string, unknown>).tokens as Record<string, number>) ?? {},
          },
        ]);
      } catch {
        // Canned miss — skip
      }
      // Simulated pacing
      await new Promise((r) => setTimeout(r, 300));
    }
    setRunning(false);
  }

  return (
    <div className="space-y-8 p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Demo Mode</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Walk through the full research pipeline on a canned auto-bidding topic.
          No API keys required — all responses are pre-recorded.
        </p>
      </div>

      <Card className="border-blue-200 dark:border-blue-800">
        <CardContent className="flex items-start gap-4 pt-6">
          <Info className="mt-0.5 size-5 shrink-0 text-blue-500" />
          <div>
            <p className="text-sm font-medium">This is a canned demo</p>
            <p className="text-xs text-muted-foreground">
              Every response below is pre-recorded. No LLM API calls are made.
              The topic is &quot;Auto-Bidding / Budget Pacing in Online Advertising&quot;.
            </p>
          </div>
        </CardContent>
      </Card>

      <button
        type="button"
        disabled={running || !entriesQuery.data}
        onClick={runDemo}
        className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
      >
        <Play className="size-4" />
        {running ? "Running demo..." : "Walk through the demo"}
      </button>

      {results.length > 0 && (
        <div className="space-y-4">
          {results.map((r, i) => (
            <Card key={i}>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    {r.stage}
                  </Badge>
                  <CardTitle className="text-sm">{r.key}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <pre className="max-h-40 overflow-auto rounded-md bg-slate-100 p-3 text-xs dark:bg-slate-900">
                  {r.response}
                </pre>
                <p className="mt-2 text-xs text-muted-foreground">
                  Tokens: {r.tokens?.prompt ?? 0} prompt + {r.tokens?.completion ?? 0} completion &middot; Cost: $0.00
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
