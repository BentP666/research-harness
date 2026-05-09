"use client";

import { HelpCircle } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useT } from "@/lib/i18n-provider";
import { cn } from "@/lib/utils";

/**
 * Reusable "Why this?" popover to demystify AI output.
 * Attach to any AI-generated claim, gap, recommendation, score.
 *
 * Usage:
 *   <WhyPopover
 *     title="Why this gap?"
 *     reasoning="Based on 12 papers; 3 explicitly state no benchmark exists."
 *     evidence={[{ label: "Smith et al. 2024", href: "/papers/42" }]}
 *     confidence={0.87}
 *   />
 */
export function WhyPopover({
  title,
  reasoning,
  evidence = [],
  confidence,
  variant = "icon",
  className,
}: {
  title: string;
  reasoning: string;
  evidence?: Array<{ label: string; href?: string; snippet?: string }>;
  confidence?: number;
  variant?: "icon" | "text";
  className?: string;
}) {
  const { t } = useT();

  return (
    <Popover>
      <PopoverTrigger
        render={
          <button
            type="button"
            className={cn(
              "inline-flex items-center gap-1 rounded-full text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground",
              variant === "icon" ? "p-0.5" : "px-2 py-0.5 hover:bg-muted",
              className
            )}
          >
            <HelpCircle className="size-3" />
            {variant === "text" && <span>{t("common.whyThis")}</span>}
          </button>
        }
      />
      <PopoverContent className="w-80 p-4" align="start">
        <div className="space-y-3">
          <div>
            <p className="text-sm font-semibold">{title}</p>
            {typeof confidence === "number" && (
              <div className="mt-1 flex items-center gap-2">
                <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "absolute inset-y-0 left-0 rounded-full",
                      confidence >= 0.75
                        ? "bg-emerald-500"
                        : confidence >= 0.5
                          ? "bg-amber-500"
                          : "bg-red-400"
                    )}
                    style={{ width: `${Math.min(100, confidence * 100)}%` }}
                  />
                </div>
                <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                  {(confidence * 100).toFixed(0)}%
                </span>
              </div>
            )}
          </div>

          <p className="text-xs leading-relaxed text-muted-foreground">
            {reasoning}
          </p>

          {evidence.length > 0 && (
            <div className="space-y-1 border-t pt-2">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Evidence
              </p>
              <ul className="space-y-1">
                {evidence.map((e, i) =>
                  e.href ? (
                    <li key={i}>
                      <a
                        href={e.href}
                        className="block rounded-md px-2 py-1 text-[11px] leading-relaxed hover:bg-muted"
                      >
                        <span className="font-medium">{e.label}</span>
                        {e.snippet && (
                          <span className="block text-muted-foreground">
                            {e.snippet}
                          </span>
                        )}
                      </a>
                    </li>
                  ) : (
                    <li
                      key={i}
                      className="rounded-md px-2 py-1 text-[11px] leading-relaxed"
                    >
                      <span className="font-medium">{e.label}</span>
                      {e.snippet && (
                        <span className="block text-muted-foreground">
                          {e.snippet}
                        </span>
                      )}
                    </li>
                  )
                )}
              </ul>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
