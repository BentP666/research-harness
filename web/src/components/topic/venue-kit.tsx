"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  MapPin, AlertCircle, Loader2, RefreshCw, ChevronDown, ChevronUp,
  BookOpen, Quote, FileText,
} from "lucide-react";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n-provider";
import {
  fetchVenueDecision, decideVenue,
  fetchVenueStyleKit, buildVenueStyleKit,
} from "@/lib/api";

interface Props {
  topicId: number;
}

export function VenueDecisionBanner({ topicId }: Props) {
  const { t } = useT();
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  const query = useQuery({
    queryKey: ["venue-decision", topicId],
    queryFn: () => fetchVenueDecision(topicId),
  });

  const decideMut = useMutation({
    mutationFn: () => decideVenue(topicId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["venue-decision", topicId] }),
  });

  if (query.isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border bg-slate-50 p-3 text-sm text-muted-foreground dark:bg-slate-900">
        <Loader2 className="size-4 animate-spin" /> {t("venue.loading")}
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="flex items-center gap-2 rounded-lg border-red-200 bg-red-50 p-3 text-sm text-red-600 dark:bg-red-950">
        <AlertCircle className="size-4" /> {t("venue.error")}
      </div>
    );
  }

  const data = query.data;

  if (!data) {
    return (
      <div className="flex items-center justify-between rounded-lg border bg-slate-50 p-3 dark:bg-slate-900">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <MapPin className="size-4" /> {t("venue.noDecision")}
        </div>
        <button
          onClick={() => decideMut.mutate()}
          disabled={decideMut.isPending}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {decideMut.isPending ? t("venue.deciding") : t("venue.decide")}
        </button>
      </div>
    );
  }

  const risks = data.fit_risk || [];

  return (
    <div className="rounded-lg border bg-slate-50 p-3 dark:bg-slate-900">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <MapPin className="size-4 text-blue-600" />
          <span className="text-sm font-semibold">{data.decided_venue}</span>
          {risks.length > 0 && (
            <Badge variant="outline" className="border-orange-300 bg-orange-50 text-orange-700 text-xs">
              {risks.length} {t("venue.risks")}
            </Badge>
          )}
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="p-1 text-muted-foreground hover:text-foreground"
        >
          {expanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
        </button>
      </div>
      {expanded && (
        <div className="mt-2 space-y-2 text-xs text-muted-foreground">
          <pre className="rounded bg-slate-100 p-2 dark:bg-slate-800">
            {JSON.stringify(data.decision_basis, null, 2)}
          </pre>
          {risks.map((r, i) => (
            <p key={i} className="text-orange-600">{r}</p>
          ))}
        </div>
      )}
    </div>
  );
}

export function VenueStyleKitCard({ topicId }: Props) {
  const { t } = useT();
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: ["venue-style-kit", topicId],
    queryFn: () => fetchVenueStyleKit(topicId),
  });

  const buildMut = useMutation({
    mutationFn: () => buildVenueStyleKit(topicId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["venue-style-kit", topicId] }),
  });

  if (query.isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> {t("styleKit.loading")}
        </CardContent>
      </Card>
    );
  }

  if (query.isError) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-4 text-sm text-red-600 dark:text-red-400">
          <AlertCircle className="size-4" /> {t("styleKit.error")}
        </CardContent>
      </Card>
    );
  }

  const data = query.data;

  if (!data) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-6">
          <BookOpen className="size-10 text-slate-300" />
          <p className="text-sm text-muted-foreground">{t("styleKit.empty")}</p>
          <button
            onClick={() => buildMut.mutate()}
            disabled={buildMut.isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {buildMut.isPending ? t("styleKit.building") : t("styleKit.build")}
          </button>
          {buildMut.isError && (
            <p className="max-w-md text-center text-xs text-red-500">
              {(buildMut.error as Error).message}
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  const sections = data.avg_section_lengths || {};
  const hedging = data.hedging_terms || [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">{t("styleKit.title")}</CardTitle>
        <button
          onClick={() => buildMut.mutate()}
          disabled={buildMut.isPending}
          className="rounded-md border p-1.5 text-xs hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50"
        >
          <RefreshCw className={`size-3.5 ${buildMut.isPending ? "animate-spin" : ""}`} />
        </button>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <div className="rounded-lg border p-3 text-center">
            <FileText className="mx-auto size-4 text-muted-foreground" />
            <p className="mt-1 text-lg font-semibold">{sections.introduction ?? "—"}</p>
            <p className="text-[10px] text-muted-foreground">{t("styleKit.introLength")}</p>
          </div>
          <div className="rounded-lg border p-3 text-center">
            <Quote className="mx-auto size-4 text-muted-foreground" />
            <p className="mt-1 text-lg font-semibold">{data.citation_density?.toFixed(1) ?? "—"}</p>
            <p className="text-[10px] text-muted-foreground">{t("styleKit.citationDensity")}</p>
          </div>
          <div className="rounded-lg border p-3 text-center">
            <BookOpen className="mx-auto size-4 text-muted-foreground" />
            <p className="mt-1 text-lg font-semibold">{hedging.length}</p>
            <p className="text-[10px] text-muted-foreground">{t("styleKit.hedgingTerms")}</p>
          </div>
          <div className="rounded-lg border p-3 text-center">
            <MapPin className="mx-auto size-4 text-muted-foreground" />
            <p className="mt-1 text-lg font-semibold">{data.source_paper_ids?.length ?? 0}</p>
            <p className="text-[10px] text-muted-foreground">{t("styleKit.sourcePapers")}</p>
          </div>
        </div>
        {data.source_venues && data.source_venues.length > 0 && (
          <p className="mt-2 text-[10px] text-muted-foreground">
            {t("styleKit.sourceVenues")}: {data.source_venues.join(", ")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
