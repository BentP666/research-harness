"use client";

import { Sprout, Compass, Target, Rocket, type LucideIcon } from "lucide-react";
import { useT } from "@/lib/i18n-provider";
import type { Persona } from "@/lib/api";

interface PersonaOption {
  persona: Persona;
  icon: LucideIcon;
  titleKey: string;
  scenarioKey: string;
}

const PERSONAS: PersonaOption[] = [
  {
    persona: "p1_no_domain",
    icon: Sprout,
    titleKey: "onboarding.persona.p1.title",
    scenarioKey: "onboarding.persona.p1.scenario",
  },
  {
    persona: "p2_domain_no_topic",
    icon: Compass,
    titleKey: "onboarding.persona.p2.title",
    scenarioKey: "onboarding.persona.p2.scenario",
  },
  {
    persona: "p3_topic_weak",
    icon: Target,
    titleKey: "onboarding.persona.p3.title",
    scenarioKey: "onboarding.persona.p3.scenario",
  },
  {
    persona: "p4_topic_strong",
    icon: Rocket,
    titleKey: "onboarding.persona.p4.title",
    scenarioKey: "onboarding.persona.p4.scenario",
  },
];

interface Props {
  selected: Persona | null;
  onSelect: (persona: Persona) => void;
}

export default function PersonaStep({ selected, onSelect }: Props) {
  const { t } = useT();

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {PERSONAS.map(({ persona, icon: Icon, titleKey, scenarioKey }) => (
        <button
          key={persona}
          type="button"
          onClick={() => onSelect(persona)}
          className={`flex flex-col items-center gap-3 rounded-xl border-2 p-6 text-center transition-all hover:scale-105 ${
            selected === persona
              ? "border-blue-600 bg-blue-50 shadow-lg ring-2 ring-blue-600 dark:bg-blue-950"
              : "border-slate-200 hover:border-slate-300 dark:border-slate-700"
          }`}
          style={{ minHeight: 160, minWidth: 240 }}
        >
          <Icon
            className={`size-8 ${
              selected === persona
                ? "text-blue-600"
                : "text-slate-400"
            }`}
          />
          <div>
            <p className="text-sm font-semibold">{t(titleKey)}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {t(scenarioKey)}
            </p>
          </div>
        </button>
      ))}
    </div>
  );
}
