"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Compass,
  FileText,
  Loader2,
  MoveRight,
  Pencil,
  Plus,
  Search as SearchIcon,
} from "lucide-react";
import Link from "next/link";

import { createDomain, fetchDomains, fetchTopics, updateDomain, updateTopic } from "@/lib/api";
import {
  type Domain,
  type Topic,
  STAGE_BG_COLORS,
  STAGE_TEXT_COLORS,
  STAGE_LABELS,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n-provider";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

// ---------------------------------------------------------------------------
// Helpers
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
// Inline-editable name
// ---------------------------------------------------------------------------

function InlineEditName({
  value,
  onSave,
  className,
  inputClassName,
}: {
  value: string;
  onSave: (next: string) => void;
  className?: string;
  inputClassName?: string;
}) {
  const { t } = useT();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      // Small delay so the input is mounted before we focus
      requestAnimationFrame(() => inputRef.current?.select());
    }
  }, [editing, value]);

  const commit = useCallback(() => {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== value) {
      onSave(trimmed);
    }
    setEditing(false);
  }, [draft, value, onSave]);

  const cancel = useCallback(() => {
    setDraft(value);
    setEditing(false);
  }, [value]);

  if (editing) {
    return (
      <Input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit();
          } else if (e.key === "Escape") {
            e.preventDefault();
            cancel();
          }
        }}
        onBlur={commit}
        className={cn("h-7 px-1.5 text-sm", inputClassName)}
      />
    );
  }

  return (
    <span
      className={cn("group/edit inline-flex items-center gap-1 cursor-pointer", className)}
      onDoubleClick={() => {
        setDraft(value);
        setEditing(true);
      }}
      title={t("research.editHint")}
    >
      <span>{value}</span>
      <Pencil className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover/edit:opacity-100" />
    </span>
  );
}

// ---------------------------------------------------------------------------
// Topic card
// ---------------------------------------------------------------------------

function TopicCard({
  topic,
  onAssignClick,
  onRename,
}: {
  topic: Topic;
  onAssignClick?: (topic: Topic) => void;
  onRename?: (topicId: number, name: string) => void;
}) {
  const isOrphan = topic.domain_id == null;

  return (
    <Card
      className={cn(
        "transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:ring-2 hover:ring-blue-500/20",
        isOrphan && "border-amber-400/60 dark:border-amber-500/40"
      )}
    >
      <CardHeader>
        {onRename ? (
          <CardTitle>
            <InlineEditName
              value={topic.name}
              onSave={(name) => onRename(topic.id, name)}
            />
          </CardTitle>
        ) : (
          <Link href={`/topics/${topic.id}`} className="block">
            <CardTitle>{topic.name}</CardTitle>
          </Link>
        )}
        <CardDescription className="truncate">
          {topic.domain_name ? (
            topic.domain_name
          ) : (
            <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="size-3" />
              No domain
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <Link href={`/topics/${topic.id}`} className="block">
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {topic.current_stage ? (
              <Badge
                variant="secondary"
                className={cn(
                  "h-5 text-[11px] font-medium",
                  STAGE_BG_COLORS[topic.current_stage],
                  STAGE_TEXT_COLORS[topic.current_stage],
                )}
              >
                {STAGE_LABELS[topic.current_stage]}
              </Badge>
            ) : null}
            <Badge variant="secondary" className="text-xs">
              {topic.paper_count} paper{topic.paper_count !== 1 ? "s" : ""}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Created {formatRelative(topic.created_at)}
          </p>
        </CardContent>
      </Link>
      <div className="border-t px-4 py-2">
        <Link
          href={`/topics/${topic.id}/reports`}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-foreground/80 hover:bg-muted hover:text-foreground"
          onClick={(e) => e.stopPropagation()}
        >
          <FileText className="size-3.5" />
          Generate advisor report
          <MoveRight className="size-3 opacity-60" />
        </Link>
      </div>
      {isOrphan && onAssignClick && (
        <div className="border-t px-4 py-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start text-amber-700 dark:text-amber-400"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onAssignClick(topic);
            }}
          >
            <MoveRight className="size-4" data-icon="inline-start" />
            Assign to domain
          </Button>
        </div>
      )}
    </Card>
  );
}

function TopicCardSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-4 w-48" />
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-16 rounded-full" />
        </div>
        <Skeleton className="h-3 w-24" />
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Assign-domain dialog (kept identical to old /topics page)
// ---------------------------------------------------------------------------

type AssignMode = "existing" | "new";

function AssignDomainDialogBody({
  topic,
  domains,
  onClose,
}: {
  topic: Topic;
  domains: Domain[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<AssignMode>(
    domains.length > 0 ? "existing" : "new"
  );
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const assign = useMutation({
    mutationFn: async (domainId: number) => {
      return updateTopic(topic.id, { domain_id: domainId });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      queryClient.invalidateQueries({ queryKey: ["domains"] });
      onClose();
    },
    onError: (e) => {
      setError(e instanceof Error ? e.message : "Failed to assign.");
    },
  });

  async function handleConfirm() {
    setError(null);
    try {
      let domainId: number;
      if (mode === "existing") {
        if (selectedId == null) {
          setError("Pick a domain.");
          return;
        }
        domainId = selectedId;
      } else {
        const name = newName.trim();
        if (!name) {
          setError("Domain name is required.");
          return;
        }
        const created = await createDomain({ name });
        queryClient.invalidateQueries({ queryKey: ["domains"] });
        domainId = created.id;
      }
      assign.mutate(domainId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create domain.");
    }
  }

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Assign to domain</DialogTitle>
        <DialogDescription>
          Move <span className="font-medium">{topic.name}</span> into a domain.
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4">
        <div className="flex gap-2">
          <Button
            variant={mode === "existing" ? "default" : "outline"}
            size="sm"
            onClick={() => setMode("existing")}
            disabled={domains.length === 0}
          >
            Use existing
          </Button>
          <Button
            variant={mode === "new" ? "default" : "outline"}
            size="sm"
            onClick={() => setMode("new")}
          >
            Create new
          </Button>
        </div>

        {mode === "existing" ? (
          domains.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No domains yet. Create one instead.
            </p>
          ) : (
            <select
              value={selectedId ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                setSelectedId(v ? Number(v) : null);
              }}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
            >
              <option value="">-- Choose a domain --</option>
              {domains.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.topic_count} topics)
                </option>
              ))}
            </select>
          )
        ) : (
          <div className="space-y-1.5">
            <label className="text-sm font-medium">New domain name</label>
            <Input
              placeholder="e.g., computational-advertising"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              autoFocus
            />
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-400">
            {error}
          </div>
        )}
      </div>

      <DialogFooter>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
        <Button size="sm" onClick={handleConfirm} disabled={assign.isPending}>
          {assign.isPending ? (
            <>
              <Loader2
                className="size-4 animate-spin"
                data-icon="inline-start"
              />
              Assigning...
            </>
          ) : (
            "Assign"
          )}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}

function AssignDomainDialog({
  topic,
  domains,
  onClose,
}: {
  topic: Topic | null;
  domains: Domain[];
  onClose: () => void;
}) {
  return (
    <Dialog
      open={topic !== null}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      {topic && (
        <AssignDomainDialogBody
          key={topic.id}
          topic={topic}
          domains={domains}
          onClose={onClose}
        />
      )}
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ResearchPage() {
  const { t } = useT();
  const {
    data: topics,
    isPending,
    error,
  } = useQuery({
    queryKey: ["topics"],
    queryFn: () => fetchTopics(),
  });
  const { data: domains = [] } = useQuery({
    queryKey: ["domains"],
    queryFn: fetchDomains,
  });

  const [search, setSearch] = useState("");
  const [domainFilter, setDomainFilter] = useState<number | "all" | "orphan">(
    "all"
  );
  const [assigningTopic, setAssigningTopic] = useState<Topic | null>(null);

  const queryClient = useQueryClient();

  const renameTopic = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      updateTopic(id, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topics"] });
    },
  });

  const renameDomain = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      updateDomain(id, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["domains"] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
    },
  });

  const handleRenameTopic = useCallback(
    (id: number, name: string) => renameTopic.mutate({ id, name }),
    [renameTopic],
  );

  const handleRenameDomain = useCallback(
    (id: number, name: string) => renameDomain.mutate({ id, name }),
    [renameDomain],
  );

  const { orphan, grouped } = useMemo(() => {
    const orphan: Topic[] = [];
    const grouped = new Map<number, { name: string; topics: Topic[] }>();
    const lower = search.trim().toLowerCase();

    for (const t of topics ?? []) {
      // Filter
      if (lower) {
        const hay = `${t.name} ${t.description ?? ""} ${
          t.domain_name ?? ""
        }`.toLowerCase();
        if (!hay.includes(lower)) continue;
      }
      if (domainFilter === "orphan" && t.domain_id != null) continue;
      if (
        typeof domainFilter === "number" &&
        t.domain_id !== domainFilter
      ) {
        continue;
      }

      if (t.domain_id == null) {
        orphan.push(t);
      } else {
        const entry = grouped.get(t.domain_id);
        if (entry) {
          entry.topics.push(t);
        } else {
          grouped.set(t.domain_id, {
            name: t.domain_name ?? `Domain ${t.domain_id}`,
            topics: [t],
          });
        }
      }
    }
    return { orphan, grouped };
  }, [topics, search, domainFilter]);

  const totalShown =
    orphan.length +
    Array.from(grouped.values()).reduce((acc, g) => acc + g.topics.length, 0);

  return (
    <div className="space-y-6 p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-blue-600">
            <Compass className="size-5 text-white" />
          </div>
          <div>
            <h1 className="font-serif text-3xl font-medium tracking-tight">
              {t("research.title")}
            </h1>
            <p className="text-sm text-muted-foreground">
              {t("research.subtitle")}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            render={<Link href="/domains/new/from-idea" />}
          >
            <Plus className="size-4" />
            {t("research.newDomain")}
          </Button>
          <Button size="sm" render={<Link href="/topics/new" />}>
            <Plus className="size-4" />
            {t("research.newTopic")}
          </Button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <SearchIcon className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder={t("research.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          <FilterChip
            active={domainFilter === "all"}
            onClick={() => setDomainFilter("all")}
          >
            {t("common.all")} ({topics?.length ?? 0})
          </FilterChip>
          {domains.map((d) => (
            <FilterChip
              key={d.id}
              active={domainFilter === d.id}
              onClick={() => setDomainFilter(d.id)}
            >
              {d.name} ({d.topic_count})
            </FilterChip>
          ))}
          <FilterChip
            active={domainFilter === "orphan"}
            onClick={() => setDomainFilter("orphan")}
            tone="amber"
          >
            {t("common.unassigned")}
          </FilterChip>
        </div>
      </div>

      {isPending ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <TopicCardSkeleton />
          <TopicCardSkeleton />
          <TopicCardSkeleton />
          <TopicCardSkeleton />
        </div>
      ) : error ? (
        <p className="text-sm text-muted-foreground">Failed to load topics.</p>
      ) : !topics?.length ? (
        <EmptyState />
      ) : totalShown === 0 ? (
        <p className="text-sm text-muted-foreground">
          No topics match the current filters.
        </p>
      ) : (
        <div className="space-y-8">
          {/* Unassigned — warning-tinted frame */}
          {orphan.length > 0 && (
            <section className="rounded-xl border-2 border-dashed border-amber-300 bg-amber-50/30 p-5 dark:border-amber-900/50 dark:bg-amber-950/10">
              <div className="mb-4 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="size-4 text-amber-600 dark:text-amber-400" />
                  <h2 className="text-sm font-semibold tracking-wide text-amber-800 dark:text-amber-300">
                    {t("common.unassigned")} · {orphan.length}
                  </h2>
                </div>
                <Button size="sm" variant="outline" render={<Link href="/research/reconcile" />}>
                  {t("research.reconcileCta")}
                </Button>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {orphan.map((topic) => (
                  <TopicCard
                    key={topic.id}
                    topic={topic}
                    onAssignClick={setAssigningTopic}
                    onRename={handleRenameTopic}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Grouped by domain — each in its own framed card */}
          {Array.from(grouped.entries()).map(
            ([domainId, { name, topics }]) => (
              <section
                key={domainId}
                className="rounded-xl border bg-card p-5 shadow-sm"
              >
                <div className="mb-4 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/domains/${domainId}`}
                      className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700 text-white"
                    >
                      <Compass className="size-4" />
                    </Link>
                    <div>
                      <h2 className="text-base font-semibold">
                        <InlineEditName
                          value={name}
                          onSave={(next) => handleRenameDomain(domainId, next)}
                        />
                      </h2>
                      <p className="text-[11px] text-muted-foreground">
                        {topics.length} topic{topics.length !== 1 ? "s" : ""}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {topics.map((topic) => (
                    <TopicCard key={topic.id} topic={topic} onRename={handleRenameTopic} />
                  ))}
                </div>
              </section>
            )
          )}
        </div>
      )}

      <AssignDomainDialog
        topic={assigningTopic}
        domains={domains}
        onClose={() => setAssigningTopic(null)}
      />
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  tone = "neutral",
  children,
}: {
  active: boolean;
  onClick: () => void;
  tone?: "neutral" | "amber";
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex h-7 items-center rounded-full border px-3 text-xs font-medium transition-colors",
        active
          ? tone === "amber"
            ? "border-amber-500 bg-amber-100 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
            : "border-foreground/30 bg-foreground/5 text-foreground"
          : "border-border text-muted-foreground hover:bg-muted"
      )}
    >
      {children}
    </button>
  );
}

function EmptyState() {
  const { t } = useT();
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Compass className="size-10 text-muted-foreground/50" />
      <h3 className="mt-4 text-sm font-medium text-foreground">
        {t("research.emptyTitle")}
      </h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        {t("research.emptyBody")}
      </p>
      <div className="mt-4 flex gap-2">
        <Button size="sm" render={<Link href="/domains/new/from-idea" />}>
          <Plus className="size-4" />
          {t("research.newDomain")}
        </Button>
      </div>
    </div>
  );
}
