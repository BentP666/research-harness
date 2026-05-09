"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { fetchPaper } from "@/lib/api";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  PaperDetailContent,
  PaperDetailSkeleton,
} from "./paper-detail-content";

interface PaperDrawerProps {
  paperId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Side-drawer paper detail. Mounted globally; library / topic / trends pages
 *  control which paper is shown via the `paperId` prop. Drawer doesn't fetch
 *  until it's open AND a non-null id is passed. */
export function PaperDrawer({ paperId, open, onOpenChange }: PaperDrawerProps) {
  const q = useQuery({
    queryKey: ["paper", paperId],
    queryFn: () => fetchPaper(paperId as number),
    enabled: open && paperId != null,
    staleTime: 60_000,
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="!w-full sm:!max-w-2xl overflow-y-auto"
      >
        <SheetHeader className="flex-row items-center justify-between gap-2 border-b px-6 py-3">
          <div className="flex flex-col gap-0.5">
            <SheetTitle>Paper detail</SheetTitle>
            <SheetDescription>
              {paperId != null ? `#${paperId}` : ""}
            </SheetDescription>
          </div>
          {paperId != null && (
            <Link
              href={`/papers/${paperId}`}
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mr-8"
              onClick={() => onOpenChange(false)}
            >
              Open full page
              <ArrowUpRight className="size-3" />
            </Link>
          )}
        </SheetHeader>

        <div className="px-2">
          {q.isPending && q.fetchStatus !== "idle" && <PaperDetailSkeleton />}
          {q.isError && (
            <div className="p-6 text-sm text-red-500">
              Failed to load paper: {(q.error as Error).message}
            </div>
          )}
          {q.data && <PaperDetailContent paper={q.data} compact />}
        </div>
      </SheetContent>
    </Sheet>
  );
}
