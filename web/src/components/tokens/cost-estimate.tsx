"use client";

import { Clock, DollarSign } from "lucide-react";
import { useT } from "@/lib/i18n-provider";
import { cn } from "@/lib/utils";

/**
 * Inline cost/time hint to append beside action buttons.
 *
 * Example:
 *   <Button>Verify</Button>
 *   <CostEstimate seconds={30} cost={0.02} />
 */
export function CostEstimate({
  seconds,
  cost,
  className,
  compact = false,
}: {
  seconds: number;
  cost: number;
  className?: string;
  compact?: boolean;
}) {
  const { t } = useT();

  const secondsLabel =
    seconds >= 60 ? `${Math.round(seconds / 60)}m` : `${seconds}s`;
  const costLabel = cost < 0.01 ? "<$0.01" : `$${cost.toFixed(2)}`;

  if (compact) {
    return (
      <span className={cn("text-[10px] text-muted-foreground", className)}>
        ~{secondsLabel} · ~{costLabel}
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 text-[11px] text-muted-foreground",
        className
      )}
      title={t("tokens.estimate", {
        seconds: secondsLabel,
        cost: costLabel.replace("$", ""),
      })}
    >
      <span className="inline-flex items-center gap-0.5">
        <Clock className="size-3" />
        {secondsLabel}
      </span>
      <span className="inline-flex items-center gap-0.5">
        <DollarSign className="size-3" />
        {costLabel.replace("$", "")}
      </span>
    </span>
  );
}
