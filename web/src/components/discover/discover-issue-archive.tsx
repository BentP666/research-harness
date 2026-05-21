"use client";

import Link from "next/link";
import { CalendarDays, LibraryBig } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DiscoverIssueSummary } from "@/lib/api";

export function DiscoverIssueArchive({
  issues,
  loading = false,
}: {
  issues: DiscoverIssueSummary[] | undefined;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <Card className="border-dashed">
        <CardContent className="p-5 text-sm text-muted-foreground">
          Loading RH Discover issue archive…
        </CardContent>
      </Card>
    );
  }

  if (!issues || issues.length === 0) {
    return (
      <Card className="border-dashed">
        <CardContent className="p-5 text-sm text-muted-foreground">
          No published RH Discover issues yet. Add JSON files under
          <code className="mx-1">docs/discover/issues/</code> and validate them
          with <code>rh discover validate</code>.
        </CardContent>
      </Card>
    );
  }

  return (
    <section className="space-y-3" aria-labelledby="discover-archive-title">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <LibraryBig className="size-3.5" />
            Publishable archive
          </div>
          <h2 id="discover-archive-title" className="font-serif text-2xl font-medium">
            RH Discover issues
          </h2>
        </div>
        <Badge variant="outline">{issues.length} published</Badge>
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {issues.map((issue) => (
          <Link key={issue.issue_id} href={`/discover/issues/${issue.issue_id}`}>
            <Card className="h-full transition-colors hover:bg-muted/40">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <CalendarDays className="size-3" />
                    {issue.generated_at}
                  </span>
                  <Badge variant="secondary" className="text-[10px]">
                    {issue.cadence}
                  </Badge>
                </div>
                <CardTitle className="text-base leading-tight">{issue.title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="line-clamp-2 text-xs text-muted-foreground">
                  {issue.subtitle}
                </p>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px]">
                    {issue.brief_count} briefs
                  </Badge>
                  <Badge variant="outline" className="text-[10px]">
                    {issue.status}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}
