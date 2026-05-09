"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Trash2,
  Pause,
  Play,
  CheckCircle2,
  Zap,
  Scale,
  Brain,
  Server,
} from "lucide-react";
import Link from "next/link";
import {
  fetchAgents,
  fetchAgentPairings,
  fetchLLMProviders,
  updateAgent,
  deleteAgent,
} from "@/lib/api";
import type { Agent, AgentPairing } from "@/lib/types";
import type { LLMProviderInfo, LLMTierRoute } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n-provider";

/* ------------------------------------------------------------------ */
/*  Tier metadata                                                      */
/* ------------------------------------------------------------------ */

const TIER_META: Record<
  string,
  { icon: typeof Zap; labelKey: string; descKey: string; color: string }
> = {
  light: {
    icon: Zap,
    labelKey: "agents.tierLight",
    descKey: "agents.tierLightDesc",
    color: "text-amber-500",
  },
  medium: {
    icon: Scale,
    labelKey: "agents.tierMedium",
    descKey: "agents.tierMediumDesc",
    color: "text-blue-500",
  },
  heavy: {
    icon: Brain,
    labelKey: "agents.tierHeavy",
    descKey: "agents.tierHeavyDesc",
    color: "text-purple-500",
  },
};

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function SourceBadge({
  source,
  t,
}: {
  source: string;
  t: (key: string) => string;
}) {
  const label =
    source === "env"
      ? t("agents.sourceEnv")
      : source === "config"
        ? t("agents.sourceConfig")
        : t("agents.sourceDefault");

  const variant =
    source === "env" ? "default" : source === "config" ? "secondary" : "outline";

  return (
    <Badge variant={variant} className="h-4 text-[10px] px-1.5">
      {label}
    </Badge>
  );
}

function ProviderCard({
  provider,
  t,
}: {
  provider: LLMProviderInfo;
  t: (key: string) => string;
}) {
  return (
    <Card size="sm">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-4 shrink-0 text-emerald-500" />
            <CardTitle className="text-sm">{provider.provider}</CardTitle>
          </div>
          <Badge variant="secondary" className="text-[10px]">
            {provider.family}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {t("agents.family")}: {provider.family}
          </span>
          <SourceBadge source={provider.source} t={t} />
        </div>
      </CardContent>
    </Card>
  );
}

function TierRouteCard({
  tier,
  route,
  t,
}: {
  tier: string;
  route: LLMTierRoute;
  t: (key: string) => string;
}) {
  const meta = TIER_META[tier];
  if (!meta) return null;

  const Icon = meta.icon;

  return (
    <Card size="sm">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className={`size-4 shrink-0 ${meta.color}`} />
            <CardTitle className="text-sm">{t(meta.labelKey)}</CardTitle>
          </div>
          <SourceBadge source={route.source} t={t} />
        </div>
        <CardDescription className="text-xs">
          {t(meta.descKey)}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border bg-muted/50 px-3 py-2">
          <p className="font-mono text-xs">
            {route.provider}:{route.model}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function AgentCard({
  agent,
  onToggle,
  onDelete,
  t,
}: {
  agent: Agent;
  onToggle: () => void;
  onDelete: () => void;
  t: (key: string) => string;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{agent.nickname}</CardTitle>
          <Badge variant={agent.status === "active" ? "default" : "secondary"}>
            {agent.status}
          </Badge>
        </div>
        <CardDescription>
          {agent.provider} / {agent.model}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-1">
          {Object.entries(agent.role_prefs ?? {})
            .filter(([, v]) => v)
            .map(([role]) => (
              <Badge key={role} variant="outline" className="text-xs">
                {role}
              </Badge>
            ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {t("agents.family")}: {agent.provider_family} &middot; Key:{" "}
          {agent.api_key_env}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onToggle}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            {agent.status === "active" ? (
              <Pause className="size-3" />
            ) : (
              <Play className="size-3" />
            )}
            {agent.status === "active" ? t("agents.pause") : t("agents.activate")}
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-red-500 transition-colors hover:bg-red-50 dark:hover:bg-red-950"
          >
            <Trash2 className="size-3" />
            {t("agents.delete")}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Section skeleton                                                   */
/* ------------------------------------------------------------------ */

function SectionSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i}>
          <CardHeader>
            <Skeleton className="h-5 w-32" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-12 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function AgentsPage() {
  const { t } = useT();
  const qc = useQueryClient();

  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: () => fetchAgents(),
  });
  const pairingsQuery = useQuery({
    queryKey: ["agent-pairings"],
    queryFn: () => fetchAgentPairings(),
  });
  const providersQuery = useQuery({
    queryKey: ["llm-providers"],
    queryFn: () => fetchLLMProviders(),
    staleTime: 60_000,
  });

  const toggleMut = useMutation({
    mutationFn: (agent: Agent) =>
      updateAgent(agent.id, {
        status: agent.status === "active" ? "paused" : "active",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agents"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteAgent(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      qc.invalidateQueries({ queryKey: ["agent-pairings"] });
    },
  });

  const envProviders = providersQuery.data?.providers ?? [];
  const tierRoutes = providersQuery.data?.tier_routes ?? {};
  const configLoaded = providersQuery.data?.config_loaded ?? false;

  return (
    <div className="space-y-10 p-6 lg:p-8">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("agents.title")}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("agents.subtitle")}
          </p>
        </div>
        <Link
          href="/agents/new"
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
        >
          <Plus className="size-4" />
          {t("agents.register")}
        </Link>
      </div>

      {/* ---- Detected Providers ---- */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">{t("agents.providersTitle")}</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {t("agents.providersSubtitle")}
            </p>
          </div>
          {providersQuery.isSuccess && (
            <Badge variant={configLoaded ? "default" : "outline"}>
              <Server className="size-3" />
              {configLoaded
                ? t("agents.configLoaded")
                : t("agents.configNotLoaded")}
            </Badge>
          )}
        </div>

        {providersQuery.isPending ? (
          <SectionSkeleton count={3} />
        ) : envProviders.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {envProviders.map((p) => (
              <ProviderCard key={p.provider} provider={p} t={t} />
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="py-6 text-center">
              <p className="text-sm text-muted-foreground">
                {t("agents.providersEmpty")}
              </p>
            </CardContent>
          </Card>
        )}
      </section>

      {/* ---- Tier Routing ---- */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">
            {t("agents.tierRoutingTitle")}
          </h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {t("agents.tierRoutingSubtitle")}
          </p>
        </div>

        {providersQuery.isPending ? (
          <SectionSkeleton count={3} />
        ) : Object.keys(tierRoutes).length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {(["light", "medium", "heavy"] as const).map((tier) => {
              const route = tierRoutes[tier];
              if (!route) return null;
              return (
                <TierRouteCard key={tier} tier={tier} route={route} t={t} />
              );
            })}
          </div>
        ) : (
          <Card>
            <CardContent className="py-6 text-center">
              <p className="text-sm text-muted-foreground">
                {t("agents.providersEmpty")}
              </p>
            </CardContent>
          </Card>
        )}
      </section>

      {/* ---- Registered Agents ---- */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">
            {t("agents.registeredTitle")}
          </h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {t("agents.registeredSubtitle")}
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agentsQuery.isPending ? (
            <SectionSkeleton count={3} />
          ) : agentsQuery.data?.length ? (
            agentsQuery.data.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                onToggle={() => toggleMut.mutate(agent)}
                onDelete={() => deleteMut.mutate(agent.id)}
                t={t}
              />
            ))
          ) : (
            <p className="col-span-full text-sm text-muted-foreground">
              {t("agents.noAgents")}{" "}
              <Link
                href="/onboarding"
                className="text-blue-500 underline"
              >
                {t("agents.noAgentsHint")}
              </Link>
            </p>
          )}
        </div>
      </section>

      {/* ---- Agent Pairings ---- */}
      {pairingsQuery.data && pairingsQuery.data.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">{t("agents.pairings")}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {pairingsQuery.data.map((p: AgentPairing) => (
              <Card key={p.id}>
                <CardHeader>
                  <CardTitle className="text-base">{p.name}</CardTitle>
                  {p.is_global_default === 1 && <Badge>Default</Badge>}
                </CardHeader>
                <CardContent className="space-y-1 text-sm text-muted-foreground">
                  <p>
                    Generator: {p.generator_name} ({p.generator_model})
                  </p>
                  <p>
                    Judge: {p.judge_name} ({p.judge_model})
                  </p>
                  {p.challenger_name && (
                    <p>
                      Challenger: {p.challenger_name} ({p.challenger_model})
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
