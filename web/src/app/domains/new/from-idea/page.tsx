"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, Lightbulb, Sparkles } from "lucide-react";
import Link from "next/link";
import { suggestDomain, createDomain } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function FromIdeaPage() {
  const router = useRouter();
  const [idea, setIdea] = useState("");
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");

  const suggestMut = useMutation({
    mutationFn: () => suggestDomain(idea),
    onSuccess: (data) => {
      setEditName(data.suggestion.name);
      setEditDesc(data.suggestion.description);
    },
  });

  const createMut = useMutation({
    mutationFn: () => createDomain({ name: editName, description: editDesc }),
    onSuccess: (domain) => {
      router.push(`/domains/${domain.id}`);
    },
  });

  const suggestion = suggestMut.data?.suggestion;

  return (
    <div className="max-w-2xl mx-auto space-y-6 p-6 lg:p-8">
      <Link
        href="/domains"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="size-3.5" />
        Domains
      </Link>

      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Lightbulb className="size-5" />
          New Domain from Idea
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Describe your research idea and we will suggest a domain structure.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Your Research Idea</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea
            className="w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:ring-2 focus:ring-blue-500/40 focus:outline-none"
            rows={5}
            placeholder="Describe your research idea in a few sentences..."
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
          />
          <button
            type="button"
            onClick={() => suggestMut.mutate()}
            disabled={!idea.trim() || suggestMut.isPending}
            className="inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <Sparkles className="size-3.5" />
            {suggestMut.isPending ? "Analyzing..." : "Suggest Domain"}
          </button>
          {suggestMut.error && (
            <p className="text-xs text-red-600">
              {(suggestMut.error as Error).message}
            </p>
          )}
        </CardContent>
      </Card>

      {suggestion && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              Preview & Edit
              <Badge variant="outline" className="text-[10px]">
                {suggestMut.data?.source}
              </Badge>
            </CardTitle>
            <CardDescription className="text-xs">
              Edit the suggested name and description before creating.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">
                Domain Name
              </label>
              <input
                type="text"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500/40 focus:outline-none"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">
                Description
              </label>
              <textarea
                className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500/40 focus:outline-none"
                rows={3}
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
              />
            </div>
            {suggestion.keywords.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {suggestion.keywords.map((kw) => (
                  <Badge key={kw} variant="secondary" className="text-[10px]">
                    {kw}
                  </Badge>
                ))}
              </div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => createMut.mutate()}
                disabled={!editName.trim() || createMut.isPending}
                className="rounded-md px-4 py-2 text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {createMut.isPending ? "Creating..." : "Create Domain"}
              </button>
            </div>
            {createMut.error && (
              <p className="text-xs text-red-600">
                {(createMut.error as Error).message}
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
