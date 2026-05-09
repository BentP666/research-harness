"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Loader2, AlertCircle, Grid3x3, Play, Trash2,
} from "lucide-react";
import {
  fetchMethodAtoms, fetchGoals, harvestAtoms,
  deleteAtom,
} from "@/lib/api";
import type { MethodAtom, Goal } from "@/lib/api";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n-provider";

interface Props {
  topicId: number;
}

const ATOM_TYPES = [
  "loss", "data_trick", "augmentation",
  "training_schedule", "inference_heuristic", "micro_block",
] as const;

const RISK_COLORS: Record<string, string> = {
  low: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  medium: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  high: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

export default function MethodAtomsLibrary({ topicId }: Props) {
  const { t } = useT();
  const qc = useQueryClient();

  const atomsQuery = useQuery({
    queryKey: ["method-atoms", topicId],
    queryFn: () => fetchMethodAtoms(topicId),
  });

  const deleteMut = useMutation({
    mutationFn: (atomId: number) => deleteAtom(atomId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["method-atoms", topicId] }),
  });

  if (atomsQuery.isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">{t("atoms.title")}</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> {t("atoms.loading")}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (atomsQuery.isError) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">{t("atoms.title")}</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 rounded-md bg-red-50 p-3 text-sm text-red-600 dark:bg-red-950 dark:text-red-400">
            <AlertCircle className="size-4" /> {t("atoms.error")}
          </div>
        </CardContent>
      </Card>
    );
  }

  const atoms = atomsQuery.data ?? [];

  if (atoms.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">{t("atoms.title")}</CardTitle></CardHeader>
        <CardContent className="flex flex-col items-center gap-3 py-6">
          <Grid3x3 className="size-10 text-slate-300" />
          <p className="text-sm text-muted-foreground">{t("atoms.empty")}</p>
        </CardContent>
      </Card>
    );
  }

  const grouped = ATOM_TYPES.reduce((acc, type) => {
    acc[type] = atoms.filter((a) => a.atom_type === type);
    return acc;
  }, {} as Record<string, MethodAtom[]>);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("atoms.title")} ({atoms.length})</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {ATOM_TYPES.map((type) => {
          const group = grouped[type];
          if (!group || group.length === 0) return null;
          return (
            <div key={type}>
              <p className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                {type.replace("_", " ")} ({group.length})
              </p>
              <div className="space-y-1">
                {group.map((atom) => (
                  <div key={atom.id} className="flex items-center justify-between rounded border px-2 py-1.5 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{atom.name}</span>
                      <Badge variant="outline" className={`text-[10px] ${RISK_COLORS[atom.reuse_risk]}`}>
                        {atom.reuse_risk}
                      </Badge>
                    </div>
                    <button
                      onClick={() => deleteMut.mutate(atom.id)}
                      className="p-0.5 text-red-400 hover:text-red-600"
                    >
                      <Trash2 className="size-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
