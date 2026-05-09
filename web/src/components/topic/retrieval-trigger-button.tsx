"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Loader2 } from "lucide-react";
import { searchPapers } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useT } from "@/lib/i18n-provider";

const REASONS = [
  "missing_evidence",
  "weak_baseline",
  "new_atom_idea",
  "venue_pattern",
  "user_request",
] as const;

type Reason = (typeof REASONS)[number];

interface Props {
  topicId: number;
  stage: string;
  className?: string;
}

export function RetrievalTriggerButton({ topicId, stage, className }: Props) {
  const { t } = useT();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<Reason>("missing_evidence");
  const [query, setQuery] = useState("");
  const [resultMsg, setResultMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const searchMut = useMutation({
    mutationFn: () =>
      searchPapers({
        query: query.trim(),
        topic_id: topicId,
        stage,
        trigger_reason: reason,
        max_results: 20,
      }),
    onSuccess: (resp) => {
      setErrorMsg(null);
      const out = resp.output as { results?: unknown[] } | null;
      const count = Array.isArray(out?.results) ? out!.results!.length : 0;
      setResultMsg(t("retrieval.results", { count: String(count) }));
      qc.invalidateQueries({ queryKey: ["retrieval-log", topicId] });
      qc.invalidateQueries({ queryKey: ["topic-events", topicId] });
    },
    onError: (err: Error) => {
      setResultMsg(null);
      setErrorMsg(err.message || t("retrieval.error"));
    },
  });

  const handleClose = () => {
    setOpen(false);
    setQuery("");
    setResultMsg(null);
    setErrorMsg(null);
    setReason("missing_evidence");
  };

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className={className}
        aria-label={t("retrieval.trigger")}
        title={t("retrieval.trigger")}
        onClick={() => setOpen(true)}
      >
        <Search className="size-4" />
      </Button>
      <Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : handleClose())}>
        <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>{t("retrieval.modalTitle")}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <label htmlFor="rh-retrieval-reason" className="text-sm font-medium">{t("retrieval.reasonLabel")}</label>
            <div id="rh-retrieval-reason" className="flex flex-wrap gap-1.5">
              {REASONS.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setReason(r)}
                  className={`rounded-md border px-2.5 py-1 text-xs transition ${
                    reason === r
                      ? "border-blue-600 bg-blue-50 text-blue-900 dark:bg-blue-950/30 dark:text-blue-200"
                      : "border-slate-200 hover:border-slate-300 dark:border-slate-700"
                  }`}
                >
                  {t(`retrieval.reasons.${r}`)}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-2">
            <label htmlFor="rh-retrieval-query" className="text-sm font-medium">{t("retrieval.queryLabel")}</label>
            <Textarea
              id="rh-retrieval-query"
              rows={3}
              placeholder={t("retrieval.queryPlaceholder")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {resultMsg && (
            <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-800 dark:border-green-900 dark:bg-green-950/40 dark:text-green-200">
              {resultMsg} · {t("retrieval.logged")}
            </div>
          )}
          {errorMsg && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {errorMsg}
            </div>
          )}
        </div>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={handleClose}>
            {t("retrieval.cancel")}
          </Button>
          <Button
            onClick={() => searchMut.mutate()}
            disabled={!query.trim() || searchMut.isPending}
          >
            {searchMut.isPending ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                {t("retrieval.searching")}
              </>
            ) : (
              <>
                <Search className="mr-2 size-4" />
                {t("retrieval.search")}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
      </Dialog>
    </>
  );
}

export default RetrievalTriggerButton;
