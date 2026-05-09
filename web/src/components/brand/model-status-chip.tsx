"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Cpu, CheckCircle2, AlertCircle, Plus, Sparkles } from "lucide-react";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fetchAgents, fetchLLMProviders } from "@/lib/api";
import type { Agent } from "@/lib/types";
import { useT } from "@/lib/i18n-provider";
import { cn } from "@/lib/utils";

/**
 * Header-persistent model status chip. Shows:
 *  - user-registered agent personas (agent_registry), if any
 *  - system-level providers detected from env/CLI (Anthropic, OpenAI, Codex, ...)
 *  - tier routes (light/medium/heavy) so users can trace which model runs what
 * Only falls back to "demo mode" when BOTH agents and env providers are empty.
 */
export function ModelStatusChip() {
  const { t } = useT();

  const { data: agents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => fetchAgents(),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });

  const { data: providers } = useQuery({
    queryKey: ["llm-providers"],
    queryFn: () => fetchLLMProviders(),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });

  const activeAgents = (agents ?? []).filter((a) => a.status !== "archived");
  const envProviders = providers?.providers ?? [];
  const tierRoutes = providers?.tier_routes ?? {};

  const totalSources = activeAgents.length + envProviders.length;
  const demoMode = totalSources === 0;
  const healthyAgents = activeAgents.filter(
    (a) => (a.status ?? "active") === "active"
  );
  const allHealthy =
    activeAgents.length === 0 || healthyAgents.length === activeAgents.length;

  let tone: "demo" | "healthy" | "warn";
  if (demoMode) tone = "demo";
  else if (allHealthy) tone = "healthy";
  else tone = "warn";

  const toneClasses = {
    demo: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30 dark:text-amber-300 dark:border-amber-900/50",
    healthy:
      "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-900/50",
    warn: "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/30 dark:text-orange-300 dark:border-orange-900/50",
  };

  const dotClasses = {
    demo: "bg-amber-500",
    healthy: "bg-emerald-500",
    warn: "bg-orange-500",
  };

  return (
    <Popover>
      <PopoverTrigger
        render={
          <button
            type="button"
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors hover:opacity-90",
              toneClasses[tone]
            )}
          >
            <span
              className={cn("size-1.5 rounded-full animate-pulse", dotClasses[tone])}
            />
            {tone === "demo" ? (
              <>
                <Sparkles className="size-3" />
                {t("modelStatus.demoMode")}
              </>
            ) : (
              <>
                <Cpu className="size-3" />
                {t("modelStatus.connected", { count: totalSources })}
              </>
            )}
          </button>
        }
      />
      <PopoverContent align="end" className="w-96 p-3">
        <div className="space-y-3">
          <div>
            <p className="text-sm font-semibold">
              {tone === "demo"
                ? t("modelStatus.demoMode")
                : t("modelStatus.connected", { count: totalSources })}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {tone === "demo"
                ? t("modelStatus.demoModeHint")
                : tone === "warn"
                  ? t("modelStatus.noneHint")
                  : ""}
            </p>
          </div>

          {/* User-registered agent personas */}
          {activeAgents.length > 0 && (
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                {t("modelStatus.personasSection")}
              </p>
              <div className="space-y-1.5">
                {activeAgents.slice(0, 4).map((a) => (
                  <ModelRow key={a.id} agent={a} />
                ))}
                {activeAgents.length > 4 && (
                  <p className="text-[11px] text-muted-foreground">
                    +{activeAgents.length - 4} more
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Env-detected providers */}
          {envProviders.length > 0 && (
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                {t("modelStatus.providersSection")}
              </p>
              <div className="space-y-1.5">
                {envProviders.map((p) => (
                  <div
                    key={p.provider}
                    className="flex items-center justify-between rounded-md border bg-background px-2 py-1.5 text-xs"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <CheckCircle2 className="size-3.5 shrink-0 text-emerald-500" />
                      <span className="truncate font-medium">{p.provider}</span>
                    </div>
                    <Badge variant="secondary" className="h-4 text-[10px] px-1.5">
                      {p.family}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tier routes */}
          {Object.keys(tierRoutes).length > 0 && (
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                {t("modelStatus.tiersSection")}
              </p>
              <div className="space-y-1">
                {(["light", "medium", "heavy"] as const).map((tier) => {
                  const r = tierRoutes[tier];
                  if (!r) return null;
                  return (
                    <div
                      key={tier}
                      className="flex items-center justify-between text-[11px]"
                    >
                      <Badge variant="outline" className="h-4 text-[10px]">
                        {tier}
                      </Badge>
                      <span className="truncate text-muted-foreground font-mono">
                        {r.provider}:{r.model}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs flex-1"
              render={<Link href="/agents" />}
            >
              {t("modelStatus.manage")}
            </Button>
            <Button
              size="sm"
              className="h-7 text-xs flex-1"
              render={<Link href="/agents?new=1" />}
            >
              <Plus className="size-3" />
              {t("modelStatus.addModel")}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function ModelRow({ agent }: { agent: Agent }) {
  const ok = (agent.status ?? "active") === "active";
  return (
    <div className="flex items-center justify-between rounded-md border bg-background px-2 py-1.5 text-xs">
      <div className="flex items-center gap-2 min-w-0">
        {ok ? (
          <CheckCircle2 className="size-3.5 shrink-0 text-emerald-500" />
        ) : (
          <AlertCircle className="size-3.5 shrink-0 text-orange-500" />
        )}
        <span className="truncate font-medium">{agent.nickname}</span>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        <Badge variant="secondary" className="h-4 text-[10px] px-1.5">
          {agent.provider}
        </Badge>
        <span className="text-[10px] text-muted-foreground truncate max-w-[80px]">
          {agent.model}
        </span>
      </div>
    </div>
  );
}
