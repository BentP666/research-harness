"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createAgent, fetchLLMProviders } from "@/lib/api";
import {
  Card,
  CardContent,
} from "@/components/ui/card";

const FALLBACK_PROVIDERS = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "google", label: "Google / Gemini" },
  { value: "kimi", label: "Kimi (Moonshot)" },
] as const;

export default function NewAgentPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: llmData } = useQuery({
    queryKey: ["llm-providers"],
    queryFn: fetchLLMProviders,
    staleTime: 60_000,
  });
  const providerOptions = llmData?.providers?.length
    ? llmData.providers.map((p) => ({
        value: p.provider,
        label: p.display_name || p.provider,
      }))
    : FALLBACK_PROVIDERS.map((p) => ({ value: p.value, label: p.label }));
  const [form, setForm] = useState({
    nickname: "",
    provider: "anthropic",
    model: "",
    api_key_env: "ANTHROPIC_API_KEY",
    roles: { generator: true, judge: false } as Record<string, boolean>,
  });
  const [error, setError] = useState("");

  const mut = useMutation({
    mutationFn: () =>
      createAgent({
        nickname: form.nickname,
        provider: form.provider,
        model: form.model,
        api_key_env: form.api_key_env,
        role_prefs: form.roles,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      router.push("/agents");
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <div className="mx-auto max-w-lg space-y-6 p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Register Agent</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Add an LLM agent for generation, judging, or challenging.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-4 pt-6">
          <div>
            <label className="mb-1 block text-sm font-medium">Nickname</label>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              value={form.nickname}
              onChange={(e) => setForm((f) => ({ ...f, nickname: e.target.value }))}
              placeholder="e.g. opus-gen"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Provider</label>
            <select
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              value={form.provider}
              onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))}
            >
              {providerOptions.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Model</label>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              value={form.model}
              onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
              placeholder="e.g. claude-opus-4-7"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">API Key Env Var</label>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              value={form.api_key_env}
              onChange={(e) => setForm((f) => ({ ...f, api_key_env: e.target.value }))}
              placeholder="ANTHROPIC_API_KEY"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium">Roles</label>
            <div className="flex gap-3">
              {["generator", "judge", "challenger"].map((role) => (
                <label key={role} className="inline-flex items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={form.roles[role] ?? false}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        roles: { ...f.roles, [role]: e.target.checked },
                      }))
                    }
                  />
                  {role}
                </label>
              ))}
            </div>
          </div>

          {error && (
            <p className="rounded-md bg-red-50 p-2 text-sm text-red-600 dark:bg-red-950 dark:text-red-400">
              {error}
            </p>
          )}

          <button
            type="button"
            disabled={!form.nickname || !form.model || mut.isPending}
            onClick={() => mut.mutate()}
            className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            {mut.isPending ? "Registering..." : "Register Agent"}
          </button>
        </CardContent>
      </Card>
    </div>
  );
}
