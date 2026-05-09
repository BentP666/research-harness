"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Check, ChevronRight, ChevronLeft } from "lucide-react";
import {
  createAgent,
  createAgentPairing,
  fetchAgentPresets,
  updateUserPreferences,
} from "@/lib/api";
import type { Persona, VenueConstraint, ComputeBudget } from "@/lib/api";
import type { AgentPreset } from "@/lib/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n-provider";
import PersonaStep from "@/components/onboarding/persona-step";
import ConstraintsStep from "@/components/onboarding/constraints-step";

function getSteps(persona: Persona | null): string[] {
  if (!persona) return ["Persona"];
  switch (persona) {
    case "p1_no_domain":
      return ["Persona", "Domain Discovery", "Constraints", "Agents", "Done"];
    case "p2_domain_no_topic":
      return ["Persona", "Domain Selection", "Topic Hint", "Constraints", "Agents", "Done"];
    case "p3_topic_weak":
      return ["Persona", "Topic Brief", "Constraints", "Agents", "Done"];
    case "p4_topic_strong":
      return ["Persona", "Topic Brief", "Seed Material", "Constraints", "Agents", "Done"];
  }
}

type WizardData = {
  persona: Persona | null;
  domainConfidence: number;
  topicConfidence: number;
  venueConstraint: VenueConstraint;
  targetVenue: string;
  computeBudget: ComputeBudget;
  deadlineDays: number;
  seedPresent: boolean;
  rawNotes: string;
  // Legacy fields (kept for backward compat with existing steps)
  language: string;
  discipline: string;
  venueTier: string;
  agents: Array<{
    nickname: string;
    provider: string;
    model: string;
    api_key_env: string;
    role_prefs: Record<string, boolean>;
  }>;
  autonomy: string;
  qualityTier: string;
  monthlyBudget: number;
};

function StepIndicator({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`flex size-8 items-center justify-center rounded-full text-xs font-medium transition-colors ${
            i < current
              ? "bg-blue-600 text-white"
              : i === current
                ? "border-2 border-blue-600 text-blue-600"
                : "border border-slate-300 text-slate-400"
          }`}
        >
          {i < current ? <Check className="size-4" /> : i + 1}
        </div>
      ))}
    </div>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { t } = useT();
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [data, setData] = useState<WizardData>({
    persona: null,
    domainConfidence: 50,
    topicConfidence: 50,
    venueConstraint: "preferred",
    targetVenue: "",
    computeBudget: "single_gpu",
    deadlineDays: 90,
    seedPresent: false,
    rawNotes: "",
    language: "en",
    discipline: "cs",
    venueTier: "B",
    agents: [],
    autonomy: "L2",
    qualityTier: "standard",
    monthlyBudget: 100,
  });

  const steps = getSteps(data.persona);

  const presetsQuery = useQuery({
    queryKey: ["agent-presets"],
    queryFn: fetchAgentPresets,
  });

  const finishMut = useMutation({
    mutationFn: async () => {
      // Create agents
      const createdAgents: Array<{ id: number; nickname: string; provider: string }> = [];
      for (const a of data.agents) {
        const resp = await createAgent(a);
        createdAgents.push({ id: resp.id, nickname: resp.nickname, provider: resp.provider });
      }

      const gen = createdAgents.find((a) =>
        data.agents.find((d) => d.nickname === a.nickname)?.role_prefs?.generator
      );
      const judge = createdAgents.find((a) =>
        data.agents.find((d) => d.nickname === a.nickname)?.role_prefs?.judge
      );
      if (gen && judge && gen.id !== judge.id) {
        await createAgentPairing({
          name: `${gen.nickname} + ${judge.nickname}`,
          generator_agent_id: gen.id,
          judge_agent_id: judge.id,
          is_global_default: 1,
        });
      }

      await updateUserPreferences({
        language: data.language,
        discipline: data.discipline,
        default_venue_tier: data.venueTier,
        default_quality_tier: data.qualityTier,
        default_autonomy: data.autonomy,
        monthly_budget_cap_usd: data.monthlyBudget,
        onboarding_complete: 1,
      });

      // After creating topic, write intake profile
      // For now we redirect to home — topic creation happens separately
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      qc.invalidateQueries({ queryKey: ["user-preferences"] });
      router.push("/");
    },
    onError: (e: Error) => setError(e.message),
  });

  function applyPreset(preset: AgentPreset) {
    setData((d) => ({ ...d, agents: [...preset.agents] }));
  }

  function isAgentsStep(): boolean {
    return steps[step] === "Agents";
  }

  function isDoneStep(): boolean {
    return steps[step] === "Done";
  }

  function canProceed(): boolean {
    if (steps[step] === "Persona") return data.persona !== null;
    if (steps[step] === "Constraints") {
      if (data.venueConstraint === "locked" && !data.targetVenue.trim()) return false;
      return true;
    }
    if (isAgentsStep()) return data.agents.length >= 2;
    return true;
  }

  function getStepTitle(): string {
    const stepName = steps[step];
    if (stepName === "Persona") return t("onboarding.persona.stepTitle");
    if (stepName === "Constraints") return t("onboarding.constraints.stepTitle");
    return stepName;
  }

  function getStepDesc(): string {
    const stepName = steps[step];
    if (stepName === "Persona") return t("onboarding.persona.stepDesc");
    if (stepName === "Constraints") return t("onboarding.constraints.stepDesc");
    return `Step ${step + 1} of ${steps.length}`;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("onboarding.title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("onboarding.subtitle")}</p>
      </div>

      <StepIndicator current={step} total={steps.length} />

      <Card>
        <CardHeader>
          <CardTitle>{getStepTitle()}</CardTitle>
          <CardDescription>{getStepDesc()}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Persona Step */}
          {steps[step] === "Persona" && (
            <PersonaStep
              selected={data.persona}
              onSelect={(p) => setData((d) => ({ ...d, persona: p }))}
            />
          )}

          {/* Constraints Step */}
          {steps[step] === "Constraints" && (
            <ConstraintsStep
              venueConstraint={data.venueConstraint}
              targetVenue={data.targetVenue}
              computeBudget={data.computeBudget}
              deadlineDays={data.deadlineDays}
              onChangeVenueConstraint={(v) => setData((d) => ({ ...d, venueConstraint: v }))}
              onChangeTargetVenue={(v) => setData((d) => ({ ...d, targetVenue: v }))}
              onChangeComputeBudget={(v) => setData((d) => ({ ...d, computeBudget: v }))}
              onChangeDeadlineDays={(v) => setData((d) => ({ ...d, deadlineDays: v }))}
            />
          )}

          {/* Placeholder for persona-specific middle steps */}
          {(steps[step] === "Domain Discovery" || steps[step] === "Domain Selection" ||
            steps[step] === "Topic Hint" || steps[step] === "Topic Brief" ||
            steps[step] === "Seed Material") && (
            <div className="flex min-h-[200px] items-center justify-center rounded-lg border-2 border-dashed border-slate-200 dark:border-slate-700">
              <p className="text-sm text-muted-foreground">
                {steps[step]} — coming in a future iteration
              </p>
            </div>
          )}

          {/* Agents Step */}
          {isAgentsStep() && (
            <>
              <p className="text-sm text-muted-foreground">
                Register at least 2 agents. Generator and Judge must be from different provider families.
              </p>
              {presetsQuery.data && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">Quick presets:</p>
                  <div className="flex flex-wrap gap-2">
                    {presetsQuery.data.map((preset) => (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => applyPreset(preset)}
                        className="rounded-md border px-3 py-1.5 text-xs transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        {preset.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {data.agents.length > 0 && (
                <div className="space-y-2">
                  {data.agents.map((a, i) => (
                    <div key={i} className="flex items-center justify-between rounded-md border p-3 text-sm">
                      <div>
                        <span className="font-medium">{a.nickname}</span>
                        <span className="text-muted-foreground"> — {a.provider}/{a.model}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {Object.entries(a.role_prefs).filter(([, v]) => v).map(([r]) => (
                          <Badge key={r} variant="outline" className="text-xs">{r}</Badge>
                        ))}
                        <button
                          type="button"
                          onClick={() => setData((d) => ({ ...d, agents: d.agents.filter((_, j) => j !== i) }))}
                          className="text-xs text-red-500"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                {data.agents.length < 2
                  ? `Need ${2 - data.agents.length} more agent(s). Pick a preset above.`
                  : "Ready to proceed."}
              </p>
            </>
          )}

          {/* Done Step */}
          {isDoneStep() && (
            <div className="space-y-3 text-center">
              <Check className="mx-auto size-12 text-green-600" />
              <p className="text-lg font-medium">All set!</p>
              <p className="text-sm text-muted-foreground">
                Click Complete Setup to save your preferences and start researching.
              </p>
            </div>
          )}

          {error && (
            <p className="rounded-md bg-red-50 p-2 text-sm text-red-600 dark:bg-red-950 dark:text-red-400">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <button
          type="button"
          disabled={step === 0}
          onClick={() => setStep((s) => s - 1)}
          className="inline-flex items-center gap-1 rounded-md px-4 py-2 text-sm font-medium transition-colors hover:bg-slate-100 disabled:opacity-50 dark:hover:bg-slate-800"
        >
          <ChevronLeft className="size-4" /> Back
        </button>

        {!isDoneStep() ? (
          <button
            type="button"
            disabled={!canProceed()}
            onClick={() => setStep((s) => s + 1)}
            className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            Next <ChevronRight className="size-4" />
          </button>
        ) : (
          <button
            type="button"
            disabled={finishMut.isPending}
            onClick={() => finishMut.mutate()}
            className="inline-flex items-center gap-1 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
          >
            {finishMut.isPending ? "Saving..." : "Complete Setup"}
            <Check className="size-4" />
          </button>
        )}
      </div>
    </div>
  );
}
