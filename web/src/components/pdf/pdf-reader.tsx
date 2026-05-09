"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  Loader2,
  Sparkles,
  Languages,
  ScrollText,
  Scale,
  Send,
  Trash2,
  ClipboardCopy,
} from "lucide-react";
import { explainSelection, type ExplainPreset } from "@/lib/api";
import type { PaperDetail } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// EmbedPDF uses browser-only APIs (Canvas + WebAssembly). Loading via
// next/dynamic with ssr:false keeps it out of the SSR pass entirely.
const PDFViewer = dynamic(
  () => import("@embedpdf/react-pdf-viewer").then((m) => m.PDFViewer),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 size-4 animate-spin" />
        Loading PDF engine…
      </div>
    ),
  },
);

interface PresetDef {
  id: ExplainPreset;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const PRESETS: PresetDef[] = [
  { id: "explain", label: "Explain", icon: Sparkles },
  { id: "summarize", label: "Summarize", icon: ScrollText },
  { id: "translate_zh", label: "Translate to 中文", icon: Languages },
  { id: "critique", label: "Critique", icon: Scale },
];

interface ChatTurn {
  id: string;
  preset: ExplainPreset | null;
  customPrompt: string | null;
  selection: string;
  response: string;
  status: "pending" | "ok" | "error";
  error?: string;
  meta?: { model?: string | null; provider?: string | null };
}

interface PdfReaderProps {
  paper: PaperDetail;
  pdfUrl: string;
}

export function PdfReader({ paper, pdfUrl }: PdfReaderProps) {
  const [selectedText, setSelectedText] = useState<string>("");
  const [customPrompt, setCustomPrompt] = useState<string>("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [pending, setPending] = useState<boolean>(false);
  // Holds the EmbedPDF plugin registry once the viewer is ready. Typed as
  // unknown — the public surface is unstable across versions and we only
  // use string-keyed plugin lookup below, guarded by runtime checks.
  const registryRef = useRef<unknown>(null);

  // Capture the current selection from EmbedPDF's selection plugin.
  //
  // EmbedPDF's React hook surfaces this as `provides`, but with the raw
  // registry returned by onReady we have to reach for `_capability` (or
  // call `buildCapability()`). window.getSelection() is useless here —
  // PDF text lives in a shadow DOM canvas/text-layer combo and is not
  // exposed to the document-level selection.
  const captureSelection = useCallback(async (): Promise<string> => {
    type Capability = { getSelectedText?: () => unknown };
    type SelectionPluginInstance = {
      _capability?: Capability;
      buildCapability?: () => Capability;
    };
    type Registry = {
      getPlugin?: (id: string) => SelectionPluginInstance | null;
    };
    const reg = registryRef.current as Registry | null;
    const plugin = reg?.getPlugin?.("selection") ?? null;
    const cap = plugin?._capability ?? plugin?.buildCapability?.();
    if (!cap?.getSelectedText) return "";
    try {
      const task = cap.getSelectedText() as
        | { toPromise?: () => Promise<unknown> }
        | Promise<unknown>;
      const promise =
        typeof (task as { toPromise?: unknown }).toPromise === "function"
          ? (task as { toPromise: () => Promise<unknown> }).toPromise()
          : (task as Promise<unknown>);
      const result = await promise;
      if (Array.isArray(result)) {
        return result
          .filter((s): s is string => typeof s === "string" && s.length > 0)
          .join(" ");
      }
      if (typeof result === "string") return result;
    } catch {
      // selection plugin throws when nothing is selected — that's expected
    }
    return "";
  }, []);

  // Poll the document selection so the sidebar always reflects whatever the
  // user has highlighted. EmbedPDF lives in a shadow root in some configs,
  // so a 400ms polling cadence is the cheapest portable signal.
  useEffect(() => {
    let alive = true;
    const tick = () => {
      if (!alive) return;
      void captureSelection().then((t) => {
        if (alive && t && t !== selectedText) setSelectedText(t);
      });
    };
    const handle = window.setInterval(tick, 400);
    return () => {
      alive = false;
      window.clearInterval(handle);
    };
  }, [captureSelection, selectedText]);

  const runPrompt = useCallback(
    async (preset: ExplainPreset | null, prompt: string | null) => {
      const passage = selectedText.trim();
      if (!passage) return;
      const id = crypto.randomUUID();
      const turn: ChatTurn = {
        id,
        preset,
        customPrompt: prompt,
        selection: passage,
        response: "",
        status: "pending",
      };
      setTurns((prev) => [...prev, turn]);
      setPending(true);
      try {
        const res = await explainSelection({
          text: passage,
          preset: preset ?? undefined,
          custom_prompt: prompt ?? undefined,
          paper_title: paper.title,
          paper_id: paper.id,
          tier: "medium",
        });
        setTurns((prev) =>
          prev.map((t) =>
            t.id === id
              ? {
                  ...t,
                  status: "ok",
                  response: res.response,
                  meta: {
                    model: res.usage?.model ?? null,
                    provider: res.usage?.provider ?? null,
                  },
                }
              : t,
          ),
        );
      } catch (err) {
        setTurns((prev) =>
          prev.map((t) =>
            t.id === id
              ? {
                  ...t,
                  status: "error",
                  error: err instanceof Error ? err.message : String(err),
                }
              : t,
          ),
        );
      } finally {
        setPending(false);
      }
    },
    [selectedText, paper.title, paper.id],
  );

  const onCustomSubmit = useCallback(() => {
    const trimmed = customPrompt.trim();
    if (!trimmed) return;
    void runPrompt(null, trimmed);
    setCustomPrompt("");
  }, [customPrompt, runPrompt]);

  const viewerConfig = useMemo(
    () => ({
      src: pdfUrl,
      theme: { preference: "system" as const },
    }),
    [pdfUrl],
  );

  return (
    <div className="grid h-[calc(100vh-3.5rem)] grid-cols-[minmax(0,1fr)_24rem] gap-0 overflow-hidden">
      <div className="relative h-full min-h-0 border-r border-border bg-muted/20">
        <PDFViewer
          config={viewerConfig}
          style={{ width: "100%", height: "100%" }}
          onReady={(registry) => {
            registryRef.current = registry;
          }}
        />
      </div>

      <aside className="flex h-full min-h-0 flex-col bg-card">
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-primary" />
            <span className="text-sm font-semibold">AI Assistant</span>
          </div>
          {turns.length > 0 && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setTurns([])}
              className="h-7 px-2 text-xs"
            >
              <Trash2 className="size-3" />
              Clear
            </Button>
          )}
        </header>

        <SelectionPanel
          text={selectedText}
          onClear={() => setSelectedText("")}
        />

        <div className="border-b border-border px-4 py-3">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Quick actions
          </div>
          <div className="grid grid-cols-2 gap-2">
            {PRESETS.map((p) => (
              <Button
                key={p.id}
                size="sm"
                variant="outline"
                disabled={!selectedText || pending}
                onClick={() => void runPrompt(p.id, null)}
                className="h-8 justify-start text-xs"
              >
                <p.icon className="size-3" />
                {p.label}
              </Button>
            ))}
          </div>
        </div>

        <div className="border-b border-border px-4 py-3">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Custom prompt
          </div>
          <Textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            placeholder="Ask anything about the selected text…"
            className="mb-2 min-h-16 resize-none text-sm"
            disabled={!selectedText || pending}
          />
          <Button
            size="sm"
            disabled={!selectedText || !customPrompt.trim() || pending}
            onClick={onCustomSubmit}
            className="h-8 w-full"
          >
            {pending ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <Send className="size-3" />
            )}
            Run
          </Button>
        </div>

        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-3 p-4">
            {turns.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Select text in the PDF on the left, then choose an action above.
              </p>
            ) : (
              turns.map((t) => <ChatTurnView key={t.id} turn={t} />)
            )}
          </div>
        </ScrollArea>
      </aside>
    </div>
  );
}

function SelectionPanel({
  text,
  onClear,
}: {
  text: string;
  onClear: () => void;
}) {
  return (
    <div className="border-b border-border px-4 py-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Current selection
        </span>
        {text && (
          <Button
            size="sm"
            variant="ghost"
            onClick={onClear}
            className="h-6 px-1.5 text-xs"
          >
            <Trash2 className="size-3" />
          </Button>
        )}
      </div>
      <div
        className={cn(
          "max-h-32 overflow-y-auto rounded-md border border-dashed border-border px-3 py-2 text-xs leading-relaxed",
          text ? "text-foreground" : "text-muted-foreground italic",
        )}
      >
        {text || "Highlight text in the PDF to capture it here."}
      </div>
    </div>
  );
}

function ChatTurnView({ turn }: { turn: ChatTurn }) {
  const presetLabel = turn.preset
    ? PRESETS.find((p) => p.id === turn.preset)?.label
    : null;
  return (
    <div className="space-y-2 rounded-md border border-border bg-background p-3">
      <div className="flex items-center justify-between gap-2">
        <Badge variant="secondary" className="h-5 text-[10px] font-normal">
          {presetLabel ?? "Custom"}
        </Badge>
        {turn.meta?.model && (
          <span className="text-[10px] text-muted-foreground">
            {turn.meta.provider ?? "?"}/{turn.meta.model}
          </span>
        )}
      </div>
      {turn.customPrompt && (
        <p className="text-xs italic text-muted-foreground">
          “{turn.customPrompt}”
        </p>
      )}
      <p className="line-clamp-3 rounded bg-muted/50 px-2 py-1 text-[11px] text-muted-foreground">
        {turn.selection}
      </p>
      {turn.status === "pending" && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3 animate-spin" />
          Thinking…
        </div>
      )}
      {turn.status === "ok" && (
        <div className="space-y-2">
          <p className="whitespace-pre-wrap text-xs leading-relaxed text-foreground">
            {turn.response}
          </p>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-1.5 text-[10px] text-muted-foreground"
            onClick={() => navigator.clipboard.writeText(turn.response)}
          >
            <ClipboardCopy className="size-3" />
            Copy
          </Button>
        </div>
      )}
      {turn.status === "error" && (
        <p className="text-xs text-destructive">{turn.error}</p>
      )}
    </div>
  );
}
