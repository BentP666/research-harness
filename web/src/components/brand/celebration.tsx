"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Celebration banner — appears on first-time milestones (first outline,
 * first draft, first verification). Auto-dismisses after 6s or on click.
 *
 * Usage:
 *   <Celebration
 *     show={firstOutlineJustGenerated}
 *     title="🎉 Your first outline is ready"
 *     body="8 sections · 14 linked papers"
 *     actions={[{ label: "Open outline", onClick: ... }]}
 *     onClose={() => setShow(false)}
 *   />
 */
export function Celebration({
  show,
  title,
  body,
  actions = [],
  onClose,
  autoHideMs = 8000,
  tone = "success",
}: {
  show: boolean;
  title: string;
  body?: string;
  actions?: Array<{ label: string; onClick?: () => void; href?: string }>;
  onClose?: () => void;
  autoHideMs?: number;
  tone?: "success" | "info";
}) {
  const [internal, setInternal] = useState(show);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setInternal(show));
    return () => cancelAnimationFrame(frame);
  }, [show]);

  useEffect(() => {
    if (!internal || !autoHideMs) return;
    const id = setTimeout(() => {
      setInternal(false);
      onClose?.();
    }, autoHideMs);
    return () => clearTimeout(id);
  }, [internal, autoHideMs, onClose]);

  const toneClasses = {
    success:
      "bg-gradient-to-r from-emerald-50 via-white to-amber-50 border-emerald-200 dark:from-emerald-950/30 dark:via-slate-900 dark:to-amber-950/30 dark:border-emerald-900/50",
    info: "bg-gradient-to-r from-sky-50 via-white to-indigo-50 border-sky-200 dark:from-sky-950/30 dark:via-slate-900 dark:to-indigo-950/30 dark:border-sky-900/50",
  };

  return (
    <AnimatePresence>
      {internal && (
        <motion.div
          initial={{ opacity: 0, y: -12, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -8, scale: 0.99 }}
          transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
          className={cn(
            "relative flex items-center gap-4 overflow-hidden rounded-xl border p-4 shadow-sm",
            toneClasses[tone]
          )}
        >
          {/* Shimmer */}
          <motion.div
            className="absolute inset-0 opacity-30"
            initial={{ x: "-100%" }}
            animate={{ x: "100%" }}
            transition={{ duration: 1.6, ease: "easeInOut" }}
            style={{
              background:
                "linear-gradient(90deg, transparent, rgba(255,255,255,0.6), transparent)",
            }}
          />

          <div className="relative flex-1 space-y-0.5">
            <p className="text-sm font-semibold">{title}</p>
            {body && (
              <p className="text-xs text-muted-foreground">{body}</p>
            )}
          </div>

          {actions.length > 0 && (
            <div className="relative flex gap-2">
              {actions.map((a, i) =>
                a.href ? (
                  <a
                    key={i}
                    href={a.href}
                    className="rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/90"
                  >
                    {a.label}
                  </a>
                ) : (
                  <button
                    key={i}
                    type="button"
                    onClick={a.onClick}
                    className="rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/90"
                  >
                    {a.label}
                  </button>
                )
              )}
            </div>
          )}

          <button
            type="button"
            onClick={() => {
              setInternal(false);
              onClose?.();
            }}
            className="relative shrink-0 rounded-full p-1 text-muted-foreground hover:bg-foreground/10"
            aria-label="Close"
          >
            <X className="size-3.5" />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
