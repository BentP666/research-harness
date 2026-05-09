"use client";

import { useEffect, useState } from "react";

/**
 * Tracks `navigator.onLine` + listens to online/offline events.
 * Returns `true` while online.
 */
export function useOnline(): boolean {
  // Match SSR for the first client render. Reading navigator.onLine during
  // initial render can make OfflineIndicator appear only on the client.
  const [online, setOnline] = useState<boolean>(true);

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.queueMicrotask(() => setOnline(navigator.onLine));
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  return online;
}
