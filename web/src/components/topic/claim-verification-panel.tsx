"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Loader2,
  ShieldAlert,
  AlertTriangle,
  Eye,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  fetchContradictions,
  verifyClaims,
  type Contradiction,
} from "@/lib/api";
import { useT } from "@/lib/i18n-provider";
import { EmptyState } from "@/components/brand/empty-state";
import { CostEstimate } from "@/components/tokens/cost-estimate";
import { WhyPopover } from "@/components/brand/why-popover";

interface ClaimVerificationPanelProps {
  topicId: number;
}

export function ClaimVerificationPanel({ topicId }: ClaimVerificationPanelProps) {
  const qc = useQueryClient();
  const { t } = useT();

  const contradictionsQ = useQuery({
    queryKey: ["topic-contradictions", topicId],
    queryFn: () => fetchContradictions(topicId),
    refetchInterval: 15000,
  });

  const verifyMut = useMutation({
    mutationFn: () => verifyClaims(topicId, { pair_budget: 200, persist: true }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["topic-contradictions", topicId] });
      const out = data.output as { contradictions_found?: number } | undefined;
      const found = out?.contradictions_found ?? 0;
      toast.success(
        found > 0
          ? t("celebration.firstVerification", { contradictions: found })
          : "No contradictions — literature is consistent"
      );
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const items = contradictionsQ.data?.contradictions ?? [];
  const lastOutput = verifyMut.data?.output as
    | {
        total_claims?: number;
        pairs_considered?: number;
        pairs_checked?: number;
        contradictions_found?: number;
        flagged_for_human_review?: Array<{
          claim_id: number;
          modality: string;
        }>;
      }
    | undefined;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <ShieldAlert className="size-4" />
          Claim verification
          {items.length > 0 && (
            <span className="text-muted-foreground font-normal">
              ({items.length} contradictions)
            </span>
          )}
        </CardTitle>
        <div className="flex items-center gap-2">
          <CostEstimate seconds={30} cost={0.02} />
          <Button
            size="sm"
            onClick={() => verifyMut.mutate()}
            disabled={verifyMut.isPending}
          >
            {verifyMut.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Eye className="size-3.5" />
            )}
            {t("empty.contradictions.cta")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Last-run summary */}
        {lastOutput && (
          <div className="rounded-md border bg-muted/30 p-2 text-xs">
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              <span>
                <span className="text-muted-foreground">Claims: </span>
                <span className="font-mono">{lastOutput.total_claims ?? 0}</span>
              </span>
              <span>
                <span className="text-muted-foreground">Pairs checked: </span>
                <span className="font-mono">
                  {lastOutput.pairs_checked ?? 0} /{" "}
                  {lastOutput.pairs_considered ?? 0}
                </span>
              </span>
              <span>
                <span className="text-muted-foreground">Contradictions: </span>
                <span className="font-mono">
                  {lastOutput.contradictions_found ?? 0}
                </span>
              </span>
              <span>
                <span className="text-muted-foreground">Needs human review: </span>
                <span className="font-mono">
                  {lastOutput.flagged_for_human_review?.length ?? 0}
                </span>
              </span>
            </div>
          </div>
        )}

        {/* Contradictions list */}
        {contradictionsQ.isPending ? (
          <p className="text-xs text-muted-foreground">{t("common.loading")}</p>
        ) : items.length === 0 ? (
          <EmptyState
            icon="🔎"
            title={t("empty.contradictions.title")}
            body={t("empty.contradictions.body")}
            primary={{
              label: t("empty.contradictions.cta"),
              onClick: () => verifyMut.mutate(),
              loading: verifyMut.isPending,
              estimate: { seconds: 30, cost: 0.02 },
            }}
            className="border-none bg-transparent p-4"
          />
        ) : (
          <div className="space-y-2">
            {items.map((c) => (
              <ContradictionCard key={c.id} c={c} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ContradictionCard({ c }: { c: Contradiction }) {
  const stale = c.status === "dismissed";
  return (
    <div className="rounded-md border bg-card p-3 text-xs">
      <div className="mb-2 flex items-center gap-2">
        <AlertTriangle className="size-3.5 text-amber-500" />
        <Badge
          variant={stale ? "outline" : "destructive"}
          className="text-[10px] h-4 px-1.5"
        >
          {c.status}
        </Badge>
        <span className="text-muted-foreground">
          confidence {c.confidence.toFixed(2)}
        </span>
        <WhyPopover
          title="Why are these in conflict?"
          reasoning={
            c.conflict_reason ||
            "Two claims on the same (task, dataset, metric) report materially different numbers. I flagged it as a potential contradiction so you can check both sources yourself."
          }
          confidence={c.confidence}
          evidence={[
            c.claim_a
              ? {
                  label: `Paper ${c.claim_a.paper_id}`,
                  snippet: c.claim_a.claim_text,
                  href: `/papers/${c.claim_a.paper_id}`,
                }
              : null,
            c.claim_b
              ? {
                  label: `Paper ${c.claim_b.paper_id}`,
                  snippet: c.claim_b.claim_text,
                  href: `/papers/${c.claim_b.paper_id}`,
                }
              : null,
          ].filter(Boolean) as Array<{ label: string; href?: string; snippet?: string }>}
        />
        {c.claim_a?.modality &&
          ["figure", "table", "equation"].includes(c.claim_a.modality) && (
            <Badge variant="secondary" className="text-[10px] h-4 px-1.5">
              needs human: {c.claim_a.modality}
            </Badge>
          )}
      </div>
      {c.conflict_reason && (
        <p className="mb-2 text-[11px] text-muted-foreground">
          {c.conflict_reason}
        </p>
      )}
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        <ClaimSide label="Claim A" claim={c.claim_a} />
        <ClaimSide label="Claim B" claim={c.claim_b} />
      </div>
    </div>
  );
}

function ClaimSide({
  label,
  claim,
}: {
  label: string;
  claim: Contradiction["claim_a"];
}) {
  if (!claim) {
    return (
      <div className="rounded border border-dashed p-2 text-muted-foreground">
        {label}: missing
      </div>
    );
  }
  return (
    <div className="rounded border bg-muted/30 p-2">
      <div className="mb-1 flex items-center gap-1.5">
        <Badge variant="outline" className="text-[10px]">
          {label}
        </Badge>
        <span className="text-[10px] text-muted-foreground">
          paper {claim.paper_id}
        </span>
        {claim.modality && (
          <Badge variant="secondary" className="text-[10px]">
            {claim.modality}
          </Badge>
        )}
      </div>
      <p className="line-clamp-3">{claim.claim_text}</p>
      <div className="mt-1 flex flex-wrap gap-x-3 text-[10px] text-muted-foreground">
        {claim.task && <span>task: {claim.task}</span>}
        {claim.dataset && <span>dataset: {claim.dataset}</span>}
        {claim.metric && <span>metric: {claim.metric}</span>}
      </div>
    </div>
  );
}
