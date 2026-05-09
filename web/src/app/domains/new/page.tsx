"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Globe, Loader2 } from "lucide-react";
import Link from "next/link";

import { createDomain } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function NewDomainPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = name.trim().length > 0 && !submitting;

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const created = await createDomain({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      queryClient.invalidateQueries({ queryKey: ["domains"] });
      router.push(`/domains/${created.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create domain.");
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <div className="flex items-center gap-3">
        <div className="flex size-9 items-center justify-center rounded-lg bg-blue-600">
          <Globe className="size-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">New Domain</h1>
          <p className="text-sm text-muted-foreground">
            A domain groups related research topics.
          </p>
        </div>
      </div>

      <Card className="mx-auto max-w-2xl">
        <CardHeader>
          <CardTitle>Domain details</CardTitle>
          <CardDescription>
            You can edit or delete the domain later.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">
              Name <span className="text-red-500">*</span>
            </label>
            <Input
              placeholder="e.g., computational-advertising"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">
              Description
            </label>
            <Textarea
              placeholder="Brief description of the research domain..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-400 whitespace-pre-wrap">
              {error}
            </div>
          )}
        </CardContent>

        <div className="flex items-center justify-between border-t px-4 py-3">
          <Button variant="ghost" size="sm" render={<Link href="/domains" />}>
            Cancel
          </Button>
          <Button size="sm" onClick={handleSubmit} disabled={!canSubmit}>
            {submitting ? (
              <>
                <Loader2
                  className="size-4 animate-spin"
                  data-icon="inline-start"
                />
                Creating...
              </>
            ) : (
              "Create Domain"
            )}
          </Button>
        </div>
      </Card>
    </div>
  );
}
