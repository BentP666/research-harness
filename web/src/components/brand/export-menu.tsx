"use client";

import { Download, FileCode, FileText, Copy, CheckCheck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export interface ExportTarget {
  /** Display label */
  label: string;
  /** Icon key — string names kept simple */
  icon?: "bibtex" | "markdown" | "copy" | "download";
  /** URL to navigate to (opens in new tab) */
  href?: string;
  /** Async action for custom work (copy / share link / etc) */
  onAction?: () => Promise<void> | void;
  /** Hint text shown below the label */
  hint?: string;
}

const ICONS = {
  bibtex: FileCode,
  markdown: FileText,
  copy: Copy,
  download: Download,
};

/**
 * Generic export dropdown — one component used for paper pool exports,
 * report exports, evidence exports. Downloads via target URL or calls
 * the onAction callback.
 */
export function ExportMenu({
  label = "Export",
  targets,
}: {
  label?: string;
  targets: ExportTarget[];
}) {
  const [done, setDone] = useState<string | null>(null);

  async function handle(target: ExportTarget) {
    try {
      if (target.onAction) {
        await target.onAction();
      } else if (target.href) {
        window.open(target.href, "_blank");
      }
      setDone(target.label);
      toast.success(`${target.label} — done`);
      setTimeout(() => setDone(null), 1800);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed");
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button size="sm" variant="outline" className="gap-1.5">
            <Download className="size-3.5" />
            {label}
          </Button>
        }
      />
      <DropdownMenuContent align="end" className="w-56 p-1">
        {targets.map((target) => {
          const Icon = target.icon ? ICONS[target.icon] : Download;
          const isDone = done === target.label;
          return (
            <DropdownMenuItem
              key={target.label}
              onClick={() => handle(target)}
              className="cursor-pointer gap-2 px-2.5 py-1.5"
            >
              {isDone ? (
                <CheckCheck className="size-3.5 text-emerald-600" />
              ) : (
                <Icon className="size-3.5" />
              )}
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium">{target.label}</div>
                {target.hint && (
                  <div className="text-[10px] text-muted-foreground">
                    {target.hint}
                  </div>
                )}
              </div>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
