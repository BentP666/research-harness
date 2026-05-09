"use client";

import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { CostEstimate } from "@/components/tokens/cost-estimate";

/**
 * Consistent empty state — every "no data" moment becomes a teaching moment.
 * Pairs with i18n keys under `empty.*` but accepts explicit props for
 * ad-hoc cases.
 */
export interface EmptyStateAction {
  label: string;
  onClick?: () => void;
  href?: string;
  variant?: "default" | "outline";
  icon?: LucideIcon;
  estimate?: { seconds: number; cost: number };
  disabled?: boolean;
  loading?: boolean;
}

export interface EmptyStateProps {
  icon?: LucideIcon | string;
  title: string;
  body?: string;
  primary?: EmptyStateAction;
  secondary?: EmptyStateAction;
  className?: string;
  /** Illustration override — a ReactNode that replaces the default icon circle. */
  illustration?: React.ReactNode;
}

export function EmptyState({
  icon,
  title,
  body,
  primary,
  secondary,
  className,
  illustration,
}: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed bg-muted/30 p-8 text-center",
        className
      )}
    >
      {illustration ? (
        illustration
      ) : (
        <div className="flex size-12 items-center justify-center rounded-full bg-background ring-4 ring-muted/40">
          {typeof icon === "string" ? (
            <span className="text-2xl">{icon}</span>
          ) : icon ? (
            (() => {
              const Icon = icon as LucideIcon;
              return <Icon className="size-6 text-muted-foreground" />;
            })()
          ) : (
            <span className="text-2xl">✨</span>
          )}
        </div>
      )}

      <div className="space-y-1.5 max-w-md">
        <h3 className="text-base font-semibold tracking-tight">{title}</h3>
        {body && (
          <p className="text-sm text-muted-foreground leading-relaxed">{body}</p>
        )}
      </div>

      {(primary || secondary) && (
        <div className="flex flex-wrap items-center justify-center gap-2">
          {primary && <ActionButton action={primary} variant="default" />}
          {secondary && <ActionButton action={secondary} variant="outline" />}
        </div>
      )}
    </motion.div>
  );
}

function ActionButton({
  action,
  variant,
}: {
  action: EmptyStateAction;
  variant: "default" | "outline";
}) {
  const Icon = action.icon;
  const inner = (
    <>
      {Icon && <Icon className="size-3.5" />}
      <span>{action.label}</span>
      {action.estimate && (
        <span className="ml-1 opacity-60">
          <CostEstimate
            seconds={action.estimate.seconds}
            cost={action.estimate.cost}
            compact
          />
        </span>
      )}
    </>
  );

  if (action.href) {
    return (
      <a
        href={action.href}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-xs font-medium transition-colors",
          variant === "default"
            ? "bg-foreground text-background hover:bg-foreground/90"
            : "border bg-background hover:bg-muted"
        )}
      >
        {inner}
      </a>
    );
  }

  return (
    <Button
      size="sm"
      variant={action.variant ?? variant}
      onClick={action.onClick}
      disabled={action.disabled || action.loading}
      className="gap-1.5"
    >
      {inner}
    </Button>
  );
}
