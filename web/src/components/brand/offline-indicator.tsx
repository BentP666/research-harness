"use client";

import { AnimatePresence, motion } from "framer-motion";
import { CloudOff, Cloud } from "lucide-react";
import { useOnline } from "@/lib/use-online";
import { useEffect, useRef, useState } from "react";

/**
 * Offline indicator — surfaces in the TopBar only when offline, and briefly
 * flashes "back online" when connection recovers. Stays out of the way when
 * things are fine.
 */
export function OfflineIndicator() {
  const online = useOnline();
  const [justReconnected, setJustReconnected] = useState(false);
  const wasOfflineRef = useRef(false);

  useEffect(() => {
    if (!online) {
      wasOfflineRef.current = true;
      return;
    }
    if (!wasOfflineRef.current) return;
    // When flipping offline → online, show a 3s 'reconnected' pulse.
    wasOfflineRef.current = false;
    const show = window.setTimeout(() => setJustReconnected(true), 0);
    const hide = window.setTimeout(() => setJustReconnected(false), 3000);
    return () => {
      window.clearTimeout(show);
      window.clearTimeout(hide);
    };
  }, [online]);

  return (
    <AnimatePresence>
      {!online ? (
        <motion.div
          key="off"
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 8 }}
          className="inline-flex items-center gap-1.5 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 dark:bg-amber-950/30 dark:border-amber-900/60 dark:text-amber-300"
        >
          <CloudOff className="size-3" />
          Offline — editing local drafts
        </motion.div>
      ) : justReconnected ? (
        <motion.div
          key="on"
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 8 }}
          className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950/30 dark:border-emerald-900/60 dark:text-emerald-300"
        >
          <Cloud className="size-3" />
          Back online
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
