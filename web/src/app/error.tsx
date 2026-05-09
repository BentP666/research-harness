"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle, RotateCw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (typeof window !== "undefined") {
      console.error("[atlas:error.tsx]", error);
    }
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center gap-4 p-6 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">
        <AlertTriangle className="size-6" />
      </div>
      <h2 className="text-2xl font-semibold">Something hiccuped.</h2>
      <p className="text-sm text-muted-foreground">
        {error?.message || "An unexpected error broke this page."}
        {error?.digest ? (
          <span className="ml-2 font-mono text-xs opacity-60">
            ({error.digest})
          </span>
        ) : null}
      </p>
      <div className="flex gap-2">
        <Button onClick={() => reset()}>
          <RotateCw className="mr-2 size-4" />
          Retry
        </Button>
        <Button variant="outline" onClick={() => (window.location.href = "/")}>
          Back home
        </Button>
      </div>
    </div>
  );
}
