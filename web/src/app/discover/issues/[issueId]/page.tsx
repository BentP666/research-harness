"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DiscoverWeeklyShowcase } from "@/components/discover/discover-weekly-showcase";
import { fetchDiscoverIssue } from "@/lib/api";

export default function DiscoverIssuePage() {
  const params = useParams<{ issueId: string }>();
  const issueId = params.issueId;
  const issueQ = useQuery({
    queryKey: ["discover-issue", issueId],
    queryFn: () => fetchDiscoverIssue(issueId),
    enabled: Boolean(issueId),
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6 lg:p-10">
      <Button variant="ghost" size="sm" className="gap-1.5" render={<Link href="/discovery/digest" />}>
        <ArrowLeft className="size-3.5" />
        Back to Discovery Digest
      </Button>

      <h1 className="sr-only">RH Discover issue {issueId}</h1>

      {issueQ.isError ? (
        <Card className="border-destructive/40">
          <CardContent className="flex items-start gap-3 p-6 text-sm">
            <AlertTriangle className="mt-0.5 size-4 text-destructive" />
            <div>
              <div className="font-medium">RH Discover issue not found</div>
              <p className="mt-1 text-muted-foreground">
                Check that the issue JSON exists under docs/discover/issues and
                has status=published.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <DiscoverWeeklyShowcase
          report={issueQ.data}
          loading={issueQ.isPending}
        />
      )}
    </div>
  );
}
