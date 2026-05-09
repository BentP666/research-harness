"use client";

import { useT } from "@/lib/i18n-provider";
import type { VenueConstraint, ComputeBudget } from "@/lib/api";

interface Props {
  venueConstraint: VenueConstraint;
  targetVenue: string;
  computeBudget: ComputeBudget;
  deadlineDays: number;
  onChangeVenueConstraint: (v: VenueConstraint) => void;
  onChangeTargetVenue: (v: string) => void;
  onChangeComputeBudget: (v: ComputeBudget) => void;
  onChangeDeadlineDays: (v: number) => void;
}

const VENUE_OPTIONS: { value: VenueConstraint; labelKey: string }[] = [
  { value: "locked", labelKey: "onboarding.constraints.venue.locked" },
  { value: "preferred", labelKey: "onboarding.constraints.venue.preferred" },
  { value: "open", labelKey: "onboarding.constraints.venue.open" },
];

const COMPUTE_OPTIONS: { value: ComputeBudget; labelKey: string; descKey: string }[] = [
  { value: "cpu_only", labelKey: "onboarding.constraints.compute.cpu", descKey: "onboarding.constraints.compute.cpuDesc" },
  { value: "single_gpu", labelKey: "onboarding.constraints.compute.singleGpu", descKey: "onboarding.constraints.compute.singleGpuDesc" },
  { value: "multi_gpu", labelKey: "onboarding.constraints.compute.multiGpu", descKey: "onboarding.constraints.compute.multiGpuDesc" },
  { value: "cluster", labelKey: "onboarding.constraints.compute.cluster", descKey: "onboarding.constraints.compute.clusterDesc" },
];

export default function ConstraintsStep({
  venueConstraint,
  targetVenue,
  computeBudget,
  deadlineDays,
  onChangeVenueConstraint,
  onChangeTargetVenue,
  onChangeComputeBudget,
  onChangeDeadlineDays,
}: Props) {
  const { t } = useT();

  return (
    <div className="space-y-6">
      {/* Venue Constraint */}
      <div>
        <label className="mb-2 block text-sm font-medium">
          {t("onboarding.constraints.venueLabel")}
        </label>
        <div className="flex gap-2">
          {VENUE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChangeVenueConstraint(opt.value)}
              className={`flex-1 rounded-lg border-2 px-3 py-2 text-sm font-medium transition-colors ${
                venueConstraint === opt.value
                  ? "border-blue-600 bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                  : "border-slate-200 hover:border-slate-300 dark:border-slate-700"
              }`}
            >
              {t(opt.labelKey)}
            </button>
          ))}
        </div>
        {(venueConstraint === "locked" || venueConstraint === "preferred") && (
          <input
            type="text"
            placeholder={t("onboarding.constraints.venuePlaceholder")}
            value={targetVenue}
            onChange={(e) => onChangeTargetVenue(e.target.value)}
            className="mt-2 w-full rounded-md border px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            required={venueConstraint === "locked"}
          />
        )}
      </div>

      {/* Compute Budget */}
      <div>
        <label className="mb-2 block text-sm font-medium">
          {t("onboarding.constraints.computeLabel")}
        </label>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {COMPUTE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChangeComputeBudget(opt.value)}
              className={`flex flex-col items-center rounded-lg border-2 p-3 text-center transition-colors ${
                computeBudget === opt.value
                  ? "border-blue-600 bg-blue-50 dark:bg-blue-950"
                  : "border-slate-200 hover:border-slate-300 dark:border-slate-700"
              }`}
            >
              <span className="text-sm font-medium">{t(opt.labelKey)}</span>
              <span className="mt-1 text-xs text-muted-foreground">
                {t(opt.descKey)}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Deadline */}
      <div>
        <label className="mb-1 block text-sm font-medium">
          {t("onboarding.constraints.deadlineLabel")}
        </label>
        <select
          className="w-full rounded-md border px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
          value={deadlineDays}
          onChange={(e) => onChangeDeadlineDays(Number(e.target.value))}
        >
          <option value={30}>30 {t("onboarding.constraints.days")}</option>
          <option value={60}>60 {t("onboarding.constraints.days")}</option>
          <option value={90}>90 {t("onboarding.constraints.days")}</option>
          <option value={120}>120 {t("onboarding.constraints.days")}</option>
          <option value={180}>180 {t("onboarding.constraints.days")}</option>
          <option value={365}>365 {t("onboarding.constraints.days")}</option>
        </select>
      </div>
    </div>
  );
}
