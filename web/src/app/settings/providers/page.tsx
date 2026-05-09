"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Plug,
  Zap,
  Scale,
  Brain,
  CheckCircle2,
  XCircle,
  Loader2,
  Sparkles,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";
import {
  fetchLLMProviders,
  fetchTierSuggestions,
  testProvider,
} from "@/lib/api";
import type { LLMProviderInfo, LLMTierRoute, ProviderTestResult } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n-provider";

const TIER_ICONS: Record<string, typeof Zap> = {
  light: Zap,
  medium: Scale,
  heavy: Brain,
};

const TIER_COLORS: Record<string, string> = {
  light: "text-amber-500",
  medium: "text-blue-500",
  heavy: "text-purple-500",
};

function ProviderCard({
  provider,
  t,
  onTest,
  testResult,
  isTesting,
}: {
  provider: LLMProviderInfo;
  t: (key: string) => string;
  onTest: () => void;
  testResult: ProviderTestResult | null;
  isTesting: boolean;
}) {
  const hasKey = provider.has_key !== false;
  return (
    <Card className="relative">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">
            {provider.display_name || provider.provider}
          </CardTitle>
          <Badge
            variant={hasKey ? "default" : "outline"}
            className={
              hasKey
                ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                : "text-muted-foreground"
            }
          >
            {hasKey ? t("settings.providers.hasKey") : t("settings.providers.noKey")}
          </Badge>
        </div>
        <CardDescription className="text-xs">
          {provider.family} · {provider.source}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0 flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={!hasKey || isTesting}
          onClick={onTest}
        >
          {isTesting ? (
            <>
              <Loader2 className="size-3 mr-1 animate-spin" />
              {t("settings.providers.testing")}
            </>
          ) : (
            t("settings.providers.testConnection")
          )}
        </Button>
        {testResult && (
          <span className="flex items-center gap-1 text-xs">
            {testResult.ok ? (
              <>
                <CheckCircle2 className="size-3 text-emerald-500" />
                <span className="text-emerald-600">
                  {t("settings.providers.testOk")}
                </span>
              </>
            ) : (
              <>
                <XCircle className="size-3 text-red-500" />
                <span className="text-red-600 truncate max-w-[200px]">
                  {testResult.error || t("settings.providers.testFail")}
                </span>
              </>
            )}
          </span>
        )}
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
  route?: LLMTierRoute;
  t: (key: string) => string;
}) {
  const Icon = TIER_ICONS[tier] ?? Scale;
  const tierKey = tier === "light" ? "lightTier" : tier === "medium" ? "mediumTier" : "heavyTier";
  return (
    <div className="flex items-center gap-3 rounded-lg border p-3">
      <Icon className={`size-5 ${TIER_COLORS[tier] ?? ""}`} />
      <div className="flex-1 min-w-0">
        <div className="font-medium text-sm">{t(`settings.providers.${tierKey}`)}</div>
      </div>
      {route ? (
        <div className="text-right">
          <div className="text-sm font-mono">
            {route.provider}:{route.model}
          </div>
          <div className="text-xs text-muted-foreground">{route.source}</div>
        </div>
      ) : (
        <span className="text-xs text-muted-foreground">—</span>
      )}
    </div>
  );
}

export default function ProvidersPage() {
  const { t } = useT();
  const [testResults, setTestResults] = useState<
    Record<string, ProviderTestResult | null>
  >({});
  const [testingProvider, setTestingProvider] = useState<string | null>(null);

  const providersQuery = useQuery({
    queryKey: ["llm-providers"],
    queryFn: fetchLLMProviders,
    refetchInterval: 30_000,
  });

  const suggestMutation = useMutation({
    mutationFn: fetchTierSuggestions,
    onSuccess: () => {
      providersQuery.refetch();
    },
  });

  const handleTest = async (provider: LLMProviderInfo) => {
    setTestingProvider(provider.provider);
    setTestResults((prev) => ({ ...prev, [provider.provider]: null }));
    try {
      const model =
        provider.tier_suggestions?.medium ||
        provider.tier_suggestions?.light ||
        "";
      if (!model) return;
      const result = await testProvider({
        provider: provider.provider,
        model,
      });
      setTestResults((prev) => ({ ...prev, [provider.provider]: result }));
    } catch {
      setTestResults((prev) => ({
        ...prev,
        [provider.provider]: { ok: false, error: "Request failed" },
      }));
    } finally {
      setTestingProvider(null);
    }
  };

  const providers = providersQuery.data?.providers ?? [];
  const tierRoutes = providersQuery.data?.tier_routes ?? {};
  const isLoading = providersQuery.isLoading;

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <div>
        <Link
          href="/settings"
          className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-2"
        >
          <ArrowLeft className="size-3" />
          {t("settings.title")}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Plug className="size-5" />
          {t("settings.providers.title")}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("settings.providers.description")}
        </p>
      </div>

      {/* Detected Providers */}
      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-medium">{t("settings.providers.detectedTitle")}</h2>
          <p className="text-xs text-muted-foreground">
            {t("settings.providers.detectedSubtitle")}
          </p>
        </div>
        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-28 rounded-lg" />
            ))}
          </div>
        ) : providers.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              {t("settings.providers.noProviders")}
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {providers.map((p) => (
              <ProviderCard
                key={p.provider}
                provider={p}
                t={t}
                onTest={() => handleTest(p)}
                testResult={testResults[p.provider] ?? null}
                isTesting={testingProvider === p.provider}
              />
            ))}
          </div>
        )}
      </section>

      {/* Tier Routing */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-medium">
              {t("settings.providers.tierRoutingTitle")}
            </h2>
            <p className="text-xs text-muted-foreground">
              {t("settings.providers.tierRoutingSubtitle")}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => suggestMutation.mutate()}
            disabled={suggestMutation.isPending || providers.length === 0}
          >
            <Sparkles className="size-3 mr-1" />
            {t("settings.providers.autoSuggest")}
          </Button>
        </div>
        <div className="space-y-2">
          {["light", "medium", "heavy"].map((tier) => (
            <TierRouteCard
              key={tier}
              tier={tier}
              route={tierRoutes[tier]}
              t={t}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
