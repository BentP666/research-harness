"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { saveDraft } from "@/lib/draft-cache";
import {
  Loader2,
  FileText,
  Edit3,
  ListTree,
  AlertCircle,
  CheckCircle2,
  Clock,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { RetrievalTriggerButton } from "@/components/topic/retrieval-trigger-button";
import {
  generateOutline,
  draftSection,
  adversarialReviewSection,
  type AdversarialWeakness,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SectionName =
  | "abstract"
  | "introduction"
  | "related_work"
  | "method"
  | "experiments"
  | "results"
  | "discussion"
  | "conclusion";

const SECTION_ORDER: SectionName[] = [
  "abstract",
  "introduction",
  "related_work",
  "method",
  "experiments",
  "results",
  "discussion",
  "conclusion",
];

const SECTION_LABELS: Record<SectionName, string> = {
  abstract: "Abstract",
  introduction: "Introduction",
  related_work: "Related Work",
  method: "Method",
  experiments: "Experiments",
  results: "Results",
  discussion: "Discussion",
  conclusion: "Conclusion",
};

interface EvidenceMapEntry {
  sentence_index: number;
  sentence_text: string;
  source_paper_id: number;
  relation_type: string;
  source_span?: string;
  confidence: number;
}

interface DraftOutputShape {
  draft?: {
    section?: string;
    content?: string;
    citations_used?: number[];
    word_count?: number;
  };
  evidence_map?: EvidenceMapEntry[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface WritePanelProps {
  topicId: number;
}

export function WritePanel({ topicId }: WritePanelProps) {
  const [outlineText, setOutlineText] = useState("");
  const [outlineLocked, setOutlineLocked] = useState(false);
  const [activeSection, setActiveSection] = useState<SectionName>(
    "introduction"
  );
  const [drafts, setDrafts] = useState<
    Partial<Record<SectionName, DraftOutputShape>>
  >({});
  const [selectedSentence, setSelectedSentence] = useState<number | null>(null);
  const [adversarialBySection, setAdversarialBySection] = useState<
    Partial<Record<SectionName, AdversarialWeakness[]>>
  >({});
  const [feedback, setFeedback] = useState<{
    type: "success" | "error" | "info";
    message: string;
  } | null>(null);

  const showFeedback = (
    type: "success" | "error" | "info",
    message: string
  ) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 8000);
  };

  // Outline mutation
  const outlineMut = useMutation({
    mutationFn: () => generateOutline(topicId, { template: "neurips" }),
    onSuccess: (data) => {
      const extracted = extractOutlineText(data.output);
      setOutlineText(extracted);
      const msg = data.summary || `Outline ready (${extracted.length} chars)`;
      showFeedback("success", msg);
      toast.success("🎉 Outline ready", { description: msg });
    },
    onError: (err: Error) => {
      showFeedback("error", err.message);
      toast.error(err.message);
    },
  });

  // Section draft mutation
  const draftMut = useMutation({
    mutationFn: (section: SectionName) =>
      draftSection(topicId, {
        section,
        outline: outlineText || undefined,
      }),
    onSuccess: (data, section) => {
      const parsed = parseDraftOutput(data.output);
      setDrafts((prev) => ({ ...prev, [section]: parsed }));
      setSelectedSentence(null);
      const words = parsed.draft?.word_count ?? 0;
      const citations = parsed.draft?.citations_used?.length ?? 0;
      const msg =
        data.summary ||
        `${SECTION_LABELS[section]} drafted · ${words} words · ${citations} citations`;
      showFeedback("success", msg);
      toast.success(`✨ ${SECTION_LABELS[section]} drafted`, {
        description: `${words} words · ${citations} citations`,
      });
    },
    onError: (err: Error) => {
      showFeedback("error", err.message);
      toast.error(err.message);
    },
  });

  const adversarialMut = useMutation({
    mutationFn: (section: SectionName) => {
      const content = drafts[section]?.draft?.content ?? "";
      return adversarialReviewSection(topicId, {
        section,
        content,
        auto_open_issues: true,
      });
    },
    onSuccess: (data, section) => {
      const weaknesses = (data.weaknesses ??
        (data.output as { weaknesses?: AdversarialWeakness[] })?.weaknesses ??
        []) as AdversarialWeakness[];
      setAdversarialBySection((prev) => ({ ...prev, [section]: weaknesses }));
      const opened = data.auto_opened_issue_ids?.length ?? 0;
      showFeedback(
        "success",
        `Adversarial review for ${SECTION_LABELS[section]}: ${weaknesses.length} weaknesses${
          opened ? ` · ${opened} critical issue(s) auto-opened` : ""
        }`
      );
    },
    onError: (err: Error) => showFeedback("error", err.message),
  });

  const currentDraft = drafts[activeSection];
  const currentAdversarial = adversarialBySection[activeSection];

  // Auto-save every draft to IndexedDB so a crash/refresh/offline blip
  // doesn't lose work.
  useEffect(() => {
    const content = currentDraft?.draft?.content;
    if (!content) return;
    const handle = setTimeout(() => {
      saveDraft(topicId, activeSection, content);
    }, 800);
    return () => clearTimeout(handle);
  }, [topicId, activeSection, currentDraft?.draft?.content]);
  const evidenceFiltered =
    selectedSentence != null
      ? currentDraft?.evidence_map?.filter(
          (em) => em.sentence_index === selectedSentence
        ) ?? []
      : currentDraft?.evidence_map ?? [];
  const draftSentences = splitSentences(currentDraft?.draft?.content ?? "");

  return (
    <div className="space-y-4">
      {/* Feedback banner */}
      {feedback && (
        <div
          className={cn(
            "flex items-center gap-2 rounded-md px-3 py-2 text-sm",
            feedback.type === "success" &&
              "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300",
            feedback.type === "error" &&
              "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-300",
            feedback.type === "info" &&
              "bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300"
          )}
        >
          {feedback.type === "success" && (
            <CheckCircle2 className="size-4 shrink-0" />
          )}
          {feedback.type === "error" && (
            <AlertCircle className="size-4 shrink-0" />
          )}
          {feedback.type === "info" && (
            <Clock className="size-4 shrink-0" />
          )}
          <span className="flex-1">{feedback.message}</span>
        </div>
      )}

      <Tabs defaultValue="outline" className="space-y-3">
        <TabsList>
          <TabsTrigger value="outline">
            <ListTree className="mr-1 size-3.5" />
            Outline
          </TabsTrigger>
          <TabsTrigger value="sections">
            <Edit3 className="mr-1 size-3.5" />
            Sections
          </TabsTrigger>
        </TabsList>

        {/* Outline tab */}
        <TabsContent value="outline" className="space-y-3">
          <Card>
            <CardHeader className="flex-row items-center justify-between pb-3">
              <CardTitle className="text-sm">Paper outline</CardTitle>
              <div className="flex items-center gap-2">
                <RetrievalTriggerButton topicId={topicId} stage="write" />
                <Button
                  size="sm"
                  onClick={() => outlineMut.mutate()}
                  disabled={outlineMut.isPending || outlineLocked}
                >
                  {outlineMut.isPending ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <FileText className="size-3.5" />
                  )}
                  {outlineText ? "Regenerate" : "Generate"}
                </Button>
                {outlineText && (
                  <Button
                    size="sm"
                    variant={outlineLocked ? "outline" : "default"}
                    onClick={() => setOutlineLocked((v) => !v)}
                  >
                    {outlineLocked ? "Unlock" : "Approve"}
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <textarea
                className="min-h-[300px] w-full rounded-md border bg-background p-3 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                placeholder="Click 'Generate' to produce an outline from your topic contributions, or paste one here."
                value={outlineText}
                onChange={(e) => setOutlineText(e.target.value)}
                disabled={outlineLocked}
              />
              <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                <span>{outlineText.length} chars</span>
                {outlineLocked && (
                  <Badge variant="secondary" className="text-[10px]">
                    Approved
                  </Badge>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sections tab */}
        <TabsContent value="sections" className="space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {SECTION_ORDER.map((s) => (
              <Button
                key={s}
                size="sm"
                variant={activeSection === s ? "default" : "outline"}
                onClick={() => setActiveSection(s)}
                className="text-xs"
              >
                {SECTION_LABELS[s]}
                {drafts[s] && (
                  <CheckCircle2 className="ml-1 size-3 text-emerald-500" />
                )}
              </Button>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            {/* Draft column */}
            <Card className="lg:col-span-2">
              <CardHeader className="flex-row items-center justify-between pb-3">
                <CardTitle className="text-sm">
                  {SECTION_LABELS[activeSection]} draft
                </CardTitle>
                <div className="flex items-center gap-1.5">
                  <Button
                    size="sm"
                    onClick={() => draftMut.mutate(activeSection)}
                    disabled={draftMut.isPending}
                  >
                    {draftMut.isPending ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Edit3 className="size-3.5" />
                    )}
                    {currentDraft ? "Redraft" : "Draft"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => adversarialMut.mutate(activeSection)}
                    disabled={adversarialMut.isPending || !currentDraft?.draft?.content}
                    title="Skeptical-reviewer adversarial review"
                  >
                    {adversarialMut.isPending ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <ShieldAlert className="size-3.5" />
                    )}
                    Adversarial
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {currentDraft?.draft?.content ? (
                  <div className="space-y-2">
                    <div className="max-h-[500px] overflow-auto rounded-md border bg-muted/30 p-3 text-xs leading-relaxed">
                      {draftSentences.map((sent, idx) => {
                        const hasEvidence = currentDraft.evidence_map?.some(
                          (em) => em.sentence_index === idx
                        );
                        const isSelected = selectedSentence === idx;
                        return (
                          <span
                            key={idx}
                            role={hasEvidence ? "button" : undefined}
                            tabIndex={hasEvidence ? 0 : undefined}
                            onClick={() => {
                              if (!hasEvidence) return;
                              setSelectedSentence(isSelected ? null : idx);
                            }}
                            className={cn(
                              "inline",
                              hasEvidence && "cursor-pointer",
                              hasEvidence &&
                                "underline decoration-dotted decoration-sky-400 underline-offset-2",
                              isSelected && "bg-sky-100 dark:bg-sky-900/40"
                            )}
                          >
                            {sent}{" "}
                          </span>
                        );
                      })}
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      <span>{currentDraft.draft.word_count ?? 0} words</span>
                      <span>
                        {currentDraft.draft.citations_used?.length ?? 0}{" "}
                        citations
                      </span>
                      {selectedSentence != null && (
                        <button
                          type="button"
                          className="text-sky-600 hover:underline"
                          onClick={() => setSelectedSentence(null)}
                        >
                          Clear sentence filter (#{selectedSentence})
                        </button>
                      )}
                    </div>
                    {currentAdversarial && currentAdversarial.length > 0 && (
                      <AdversarialWeaknessList weaknesses={currentAdversarial} />
                    )}
                  </div>
                ) : (
                  <div className="flex h-[300px] items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground">
                    No draft yet. Click &quot;Draft&quot; to generate.
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Evidence sidecar column */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">
                  Evidence map
                  {selectedSentence != null && (
                    <span className="ml-1 text-xs font-normal text-muted-foreground">
                      (sentence #{selectedSentence})
                    </span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {evidenceFiltered.length > 0 ? (
                  <div className="max-h-[500px] space-y-2 overflow-auto">
                    {evidenceFiltered.map((em, i) => (
                      <div
                        key={i}
                        className="rounded-md border bg-muted/20 p-2 text-xs"
                      >
                        <div className="flex items-center gap-1.5">
                          <Badge variant="outline" className="text-[9px]">
                            {em.relation_type}
                          </Badge>
                          <span className="text-muted-foreground">
                            Sentence #{em.sentence_index}
                          </span>
                          <span className="ml-auto text-muted-foreground">
                            paper {em.source_paper_id}
                          </span>
                        </div>
                        <p className="mt-1 line-clamp-3">
                          {em.sentence_text}
                        </p>
                        {em.source_span && (
                          <p className="mt-1 border-l-2 border-sky-400 pl-2 text-[10px] italic text-muted-foreground">
                            {em.source_span}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex h-[300px] items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground">
                    {selectedSentence != null
                      ? "No evidence on this sentence."
                      : "Evidence map is empty. Generate a draft to populate."}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Output shape helpers (defensive against backend variations)
// ---------------------------------------------------------------------------

function extractOutlineText(output: unknown): string {
  if (typeof output === "string") return output;
  if (output && typeof output === "object") {
    const o = output as Record<string, unknown>;
    if (typeof o.outline === "string") return o.outline;
    if (typeof o.content === "string") return o.content;
    return JSON.stringify(output, null, 2);
  }
  return String(output ?? "");
}

function parseDraftOutput(output: unknown): DraftOutputShape {
  if (!output || typeof output !== "object") {
    return {};
  }
  const o = output as Record<string, unknown>;
  const draft = (o.draft ?? {}) as DraftOutputShape["draft"];
  const em = Array.isArray(o.evidence_map)
    ? (o.evidence_map as EvidenceMapEntry[])
    : [];
  return { draft, evidence_map: em };
}

/** Split prose into sentences, keeping terminal punctuation. Matches the
 * backend's simple sentence tokenizer used for evidence_map indices. */
function splitSentences(text: string): string[] {
  if (!text) return [];
  const parts = text.match(/[^.!?]+[.!?]+(?:\s+|$)/g);
  if (parts && parts.length > 0) return parts.map((p) => p.trim());
  return text
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
}

function AdversarialWeaknessList({
  weaknesses,
}: {
  weaknesses: AdversarialWeakness[];
}) {
  const tone: Record<string, string> = {
    critical:
      "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-300 border-red-200",
    major:
      "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300 border-amber-200",
    minor:
      "bg-slate-50 text-slate-600 dark:bg-slate-900/30 dark:text-slate-300 border-slate-200",
  };
  return (
    <div className="space-y-1.5 rounded-md border p-2 text-xs">
      <p className="font-medium">Adversarial weaknesses</p>
      {weaknesses.map((w, i) => (
        <div
          key={i}
          className={cn(
            "rounded border p-2",
            tone[w.severity] ?? tone.minor
          )}
        >
          <div className="mb-1 flex items-center gap-1.5">
            <Badge variant="outline" className="text-[9px] uppercase">
              {w.severity}
            </Badge>
            <span className="text-[10px] opacity-70">{w.category}</span>
          </div>
          <p>{w.description}</p>
          {w.evidence && (
            <p className="mt-1 border-l-2 pl-2 text-[10px] italic opacity-80">
              {w.evidence}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
