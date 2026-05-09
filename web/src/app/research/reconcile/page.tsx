"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Check,
  Loader2,
  Plus,
  Sparkles,
  Undo2,
  Wand2,
} from "lucide-react";
import { toast } from "sonner";
import { fetchDomains, fetchTopics, updateTopic, createDomain, suggestDomain } from "@/lib/api";
import type { Domain, Topic } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useT } from "@/lib/i18n-provider";

interface Suggestion {
  domain: Domain | null;
  score: number;
  reasons: string[];
}

const STOP_WORDS = new Set([
  "a", "an", "and", "or", "the", "of", "for", "with", "to", "in", "on",
  "based", "approaches", "approach", "systems", "system", "method", "methods",
]);

function tokenize(s: string): string[] {
  return (s ?? "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((w) => w.length >= 3 && !STOP_WORDS.has(w));
}

function suggest(topic: Topic, domains: Domain[]): Suggestion {
  const topicText = `${topic.name} ${topic.description ?? ""}`;
  const topicTokens = new Set(tokenize(topicText));
  if (topicTokens.size === 0 || domains.length === 0) {
    return { domain: null, score: 0, reasons: [] };
  }

  let best: Suggestion = { domain: null, score: 0, reasons: [] };
  for (const d of domains) {
    const domainText = `${d.name} ${d.description ?? ""}`;
    const domainTokens = new Set(tokenize(domainText));
    const shared: string[] = [];
    for (const t of topicTokens) {
      if (domainTokens.has(t)) shared.push(t);
    }
    const score = shared.length / Math.max(1, topicTokens.size);
    if (score > best.score) {
      best = { domain: d, score, reasons: shared.slice(0, 5) };
    }
  }
  return best;
}

export default function ReconcilePage() {
  const { t } = useT();
  const qc = useQueryClient();

  const topicsQ = useQuery({
    queryKey: ["topics"],
    queryFn: () => fetchTopics(),
  });
  const domainsQ = useQuery({
    queryKey: ["domains"],
    queryFn: fetchDomains,
  });

  const topics = topicsQ.data ?? [];
  const domains = domainsQ.data ?? [];

  const unassigned = useMemo(
    () => topics.filter((t) => t.domain_id == null),
    [topics]
  );

  const suggestions = useMemo(() => {
    const map = new Map<number, Suggestion>();
    for (const topic of unassigned) {
      map.set(topic.id, suggest(topic, domains));
    }
    return map;
  }, [unassigned, domains]);

  // Per-row override selection (user can override suggestion)
  // number → existing domain; { mode: "new"; name: string } → inline creation
  type OverrideValue = number | { mode: "new"; name: string };
  const [overrides, setOverrides] = useState<Record<number, OverrideValue>>({});
  // Track which rows are in inline-creation mode
  const [creatingRows, setCreatingRows] = useState<Set<number>>(new Set());
  // Track rows with in-flight suggestDomain calls
  const [suggestingRows, setSuggestingRows] = useState<Set<number>>(new Set());
  // Track rows with in-flight createDomain calls
  const [savingRows, setSavingRows] = useState<Set<number>>(new Set());
  // Recent apply history for undo
  const [history, setHistory] = useState<
    Array<{ topicId: number; topicName: string; previousDomain: null }>
  >([]);

  const applyMut = useMutation({
    mutationFn: ({ topicId, domainId }: { topicId: number; domainId: number }) =>
      updateTopic(topicId, { domain_id: domainId }),
    onSuccess: (_data, vars) => {
      const topic = unassigned.find((t) => t.id === vars.topicId);
      setHistory((h) => [
        { topicId: vars.topicId, topicName: topic?.name ?? "", previousDomain: null },
        ...h.slice(0, 9),
      ]);
      qc.invalidateQueries({ queryKey: ["topics"] });
      qc.invalidateQueries({ queryKey: ["domains"] });
      toast.success(t("reconcile.applied", { name: topic?.name ?? "" }));
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const undoMut = useMutation({
    mutationFn: (topicId: number) =>
      updateTopic(topicId, { domain_id: null }),
    onSuccess: (_data, topicId) => {
      setHistory((h) => h.filter((e) => e.topicId !== topicId));
      qc.invalidateQueries({ queryKey: ["topics"] });
      toast.success(t("reconcile.undone"));
    },
    onError: (err: Error) => toast.error(err.message),
  });

  function pickedDomainFor(topic: Topic): number | null {
    const ov = overrides[topic.id];
    if (ov != null && typeof ov === "number") return ov;
    if (ov != null && typeof ov === "object") return null; // in "new" mode
    const s = suggestions.get(topic.id);
    return s?.domain?.id ?? null;
  }

  // Enter inline-creation mode for a topic row
  const enterCreateMode = useCallback(
    async (topic: Topic) => {
      setCreatingRows((prev) => new Set(prev).add(topic.id));
      setOverrides((prev) => ({
        ...prev,
        [topic.id]: { mode: "new" as const, name: "" },
      }));
      // Fire-and-forget suggestion fetch
      setSuggestingRows((prev) => new Set(prev).add(topic.id));
      try {
        const idea = `${topic.name} ${topic.description ?? ""}`.trim();
        const result = await suggestDomain(idea);
        setOverrides((prev) => {
          const cur = prev[topic.id];
          // Only update if still in "new" mode (user hasn't switched away)
          if (cur != null && typeof cur === "object" && cur.mode === "new") {
            return { ...prev, [topic.id]: { mode: "new" as const, name: result.suggestion.name } };
          }
          return prev;
        });
      } catch {
        // Suggestion failed — user can still type manually
      } finally {
        setSuggestingRows((prev) => {
          const next = new Set(prev);
          next.delete(topic.id);
          return next;
        });
      }
    },
    []
  );

  // Create domain and assign in one go
  const handleCreateAndAssign = useCallback(
    async (topicId: number, name: string) => {
      if (!name.trim()) return;
      setSavingRows((prev) => new Set(prev).add(topicId));
      try {
        const newDomain = await createDomain({ name: name.trim() });
        // Assign topic to the newly created domain
        await updateTopic(topicId, { domain_id: newDomain.id });
        const topic = unassigned.find((t) => t.id === topicId);
        setHistory((h) => [
          { topicId, topicName: topic?.name ?? "", previousDomain: null },
          ...h.slice(0, 9),
        ]);
        // Exit creation mode
        setCreatingRows((prev) => {
          const next = new Set(prev);
          next.delete(topicId);
          return next;
        });
        setOverrides((prev) => {
          const { [topicId]: _, ...rest } = prev;
          return rest;
        });
        qc.invalidateQueries({ queryKey: ["topics"] });
        qc.invalidateQueries({ queryKey: ["domains"] });
        toast.success(t("reconcile.applied", { name: topic?.name ?? "" }));
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to create domain");
      } finally {
        setSavingRows((prev) => {
          const next = new Set(prev);
          next.delete(topicId);
          return next;
        });
      }
    },
    [unassigned, qc, t]
  );

  const readyCount = unassigned.filter((u) => pickedDomainFor(u) != null).length;

  async function handleApplyAll() {
    for (const topic of unassigned) {
      const domainId = pickedDomainFor(topic);
      if (domainId == null) continue;
      await applyMut.mutateAsync({ topicId: topic.id, domainId });
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="space-y-2">
        <Link
          href="/research"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" />
          {t("research.title")}
        </Link>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="flex items-center gap-2 font-serif text-3xl font-medium tracking-tight">
              <Wand2 className="size-6 text-indigo-600" />
              {t("reconcile.title")}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground max-w-2xl">
              {t("reconcile.subtitle")}
            </p>
          </div>
          {unassigned.length > 0 && (
            <Button
              onClick={handleApplyAll}
              disabled={applyMut.isPending || readyCount === 0}
              className="shrink-0"
            >
              {applyMut.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4" />
              )}
              {t("reconcile.applyAll", { count: readyCount })}
            </Button>
          )}
        </div>
      </div>

      {topicsQ.isPending || domainsQ.isPending ? (
        <div className="h-48 animate-pulse rounded-xl border bg-muted/30" />
      ) : unassigned.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center py-16 text-center">
            <div className="flex size-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
              <Check className="size-6" />
            </div>
            <h3 className="mt-4 text-base font-semibold">
              {t("reconcile.allCleanTitle")}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {t("reconcile.allCleanBody")}
            </p>
            <Button
              variant="outline"
              size="sm"
              render={<Link href="/research" />}
              className="mt-4"
            >
              {t("common.back")}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {unassigned.map((topic, i) => {
            const s = suggestions.get(topic.id);
            const currentPicked = pickedDomainFor(topic);
            return (
              <motion.div
                key={topic.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, delay: i * 0.05 }}
              >
                <Card>
                  <CardContent className="space-y-3 p-4">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="min-w-0 flex-1">
                        <h3 className="font-semibold">{topic.name}</h3>
                        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                          {topic.description || t("reconcile.noDescription")}
                        </p>
                        <p className="mt-1 text-[10px] text-muted-foreground">
                          {topic.paper_count}{" "}
                          {topic.paper_count === 1 ? "paper" : "papers"}
                        </p>
                      </div>
                      {s?.domain && (
                        <div className="text-right">
                          <Badge
                            variant="outline"
                            className="bg-indigo-50 border-indigo-300 text-indigo-700 dark:bg-indigo-950/30 dark:border-indigo-800 dark:text-indigo-300"
                          >
                            {t("reconcile.confidence", {
                              pct: Math.round(s.score * 100),
                            })}
                          </Badge>
                          {s.reasons.length > 0 && (
                            <p className="mt-1 max-w-[200px] text-[10px] text-muted-foreground truncate">
                              {t("common.whyThis")}: {s.reasons.join(", ")}
                            </p>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Low-confidence hint */}
                    {s && s.score < 0.2 && !creatingRows.has(topic.id) && (
                      <p className="text-xs text-amber-600 dark:text-amber-400">
                        {t("reconcile.lowConfidence")}
                      </p>
                    )}

                    <div className="flex items-center gap-2 flex-wrap">
                      {creatingRows.has(topic.id) ? (
                        <>
                          <div className="flex flex-col gap-1">
                            <span className="text-[10px] text-muted-foreground">
                              {t("reconcile.suggestedName")}
                            </span>
                            <Input
                              className="w-56"
                              placeholder={suggestingRows.has(topic.id) ? "..." : t("reconcile.suggestedName")}
                              disabled={suggestingRows.has(topic.id)}
                              value={
                                (() => {
                                  const ov = overrides[topic.id];
                                  return ov != null && typeof ov === "object" ? ov.name : "";
                                })()
                              }
                              onChange={(e) => {
                                const val = e.target.value;
                                setOverrides((prev) => ({
                                  ...prev,
                                  [topic.id]: { mode: "new" as const, name: val },
                                }));
                              }}
                            />
                          </div>
                          <div className="flex items-end gap-1 self-end">
                            <Button
                              size="sm"
                              onClick={() => {
                                const ov = overrides[topic.id];
                                const name = ov != null && typeof ov === "object" ? ov.name : "";
                                handleCreateAndAssign(topic.id, name);
                              }}
                              disabled={
                                savingRows.has(topic.id) ||
                                suggestingRows.has(topic.id) ||
                                (() => {
                                  const ov = overrides[topic.id];
                                  return ov == null || typeof ov !== "object" || !ov.name.trim();
                                })()
                              }
                            >
                              {savingRows.has(topic.id) ? (
                                <Loader2 className="size-3.5 animate-spin" />
                              ) : (
                                <Plus className="size-3.5" />
                              )}
                              {t("reconcile.createAndAssign")}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                setCreatingRows((prev) => {
                                  const next = new Set(prev);
                                  next.delete(topic.id);
                                  return next;
                                });
                                setOverrides((prev) => {
                                  const { [topic.id]: _, ...rest } = prev;
                                  return rest;
                                });
                              }}
                            >
                              {t("common.cancel")}
                            </Button>
                          </div>
                        </>
                      ) : (
                        <>
                          <Select
                            value={currentPicked != null ? String(currentPicked) : ""}
                            onValueChange={(v) => {
                              if (v === "__create_new__") {
                                enterCreateMode(topic);
                                return;
                              }
                              setOverrides((prev) => ({
                                ...prev,
                                [topic.id]: Number(v),
                              }));
                            }}
                          >
                            <SelectTrigger className="w-56">
                              <SelectValue placeholder={t("reconcile.pickDomain")} />
                            </SelectTrigger>
                            <SelectContent>
                              {domains.map((d) => (
                                <SelectItem key={d.id} value={String(d.id)}>
                                  {d.name}
                                  {s?.domain?.id === d.id && (
                                    <span className="ml-1 text-xs text-indigo-600">
                                      ★
                                    </span>
                                  )}
                                </SelectItem>
                              ))}
                              <SelectItem value="__create_new__" className="text-indigo-600 dark:text-indigo-400">
                                {t("reconcile.createNew")}
                              </SelectItem>
                            </SelectContent>
                          </Select>
                          <Button
                            size="sm"
                            onClick={() => {
                              const domainId = pickedDomainFor(topic);
                              if (domainId == null) return;
                              applyMut.mutate({ topicId: topic.id, domainId });
                            }}
                            disabled={applyMut.isPending || currentPicked == null}
                          >
                            {applyMut.isPending ? (
                              <Loader2 className="size-3.5 animate-spin" />
                            ) : (
                              <Check className="size-3.5" />
                            )}
                            {t("reconcile.apply")}
                          </Button>
                        </>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Undo history */}
      {history.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Undo2 className="size-4" />
              {t("reconcile.recentAssignments")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1">
              {history.map((h) => (
                <li
                  key={h.topicId}
                  className="flex items-center justify-between gap-2 text-xs"
                >
                  <span className="truncate">{h.topicName}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs"
                    onClick={() => undoMut.mutate(h.topicId)}
                    disabled={undoMut.isPending}
                  >
                    {undoMut.isPending ? (
                      <Loader2 className="size-3 animate-spin" />
                    ) : (
                      <Undo2 className="size-3" />
                    )}
                    {t("reconcile.undo")}
                  </Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
