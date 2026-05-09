"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { useT } from "@/lib/i18n-provider";

/**
 * Hero greeting on the dashboard — cinematic mesh gradient with drifting orbs,
 * time-aware greeting in serif, project count.
 *
 * Goals:
 * - Replace the cold "Dashboard" header with a moment that *feels* like an
 *   AI research partner welcoming you in.
 * - Animation is slow + ambient — not flashy. Eye drifts, doesn't react.
 */
export function TodayHero({ topicCount }: { topicCount: number }) {
  const { t, locale } = useT();

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return t("dashboard.greeting.morning");
    if (hour < 18) return t("dashboard.greeting.afternoon");
    return t("dashboard.greeting.evening");
  }, [t]);

  const prompt =
    topicCount > 0
      ? t("dashboard.activePrompt", { count: topicCount })
      : t("dashboard.noProjectsPrompt");

  const dateLabel = new Date().toLocaleDateString(
    locale === "zh" ? "zh-CN" : "en-US",
    { weekday: "long", month: "long", day: "numeric" },
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
      className="relative isolate overflow-hidden rounded-3xl border border-white/40 bg-gradient-to-br from-indigo-50/80 via-white/60 to-amber-50/50 p-8 shadow-xl shadow-indigo-500/[0.04] backdrop-blur-md sm:p-10 dark:border-white/5 dark:from-indigo-950/40 dark:via-slate-900/40 dark:to-amber-950/20"
    >
      {/* Animated mesh — three orbs drifting in slow loops */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -right-20 -top-24 size-72 rounded-full bg-indigo-400/30 blur-3xl dark:bg-indigo-500/15"
        animate={{
          x: [0, 24, -8, 0],
          y: [0, -12, 16, 0],
          scale: [1, 1.08, 0.96, 1],
        }}
        transition={{ duration: 22, ease: "easeInOut", repeat: Infinity }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -bottom-16 -left-12 size-64 rounded-full bg-violet-400/25 blur-3xl dark:bg-violet-500/15"
        animate={{
          x: [0, -18, 22, 0],
          y: [0, 14, -10, 0],
          scale: [1, 1.1, 0.92, 1],
        }}
        transition={{ duration: 26, ease: "easeInOut", repeat: Infinity }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -bottom-10 right-[20%] size-48 rounded-full bg-amber-300/30 blur-3xl dark:bg-amber-500/10"
        animate={{
          x: [0, 18, -14, 0],
          y: [0, -10, 8, 0],
          scale: [1, 1.05, 0.95, 1],
        }}
        transition={{ duration: 18, ease: "easeInOut", repeat: Infinity }}
      />

      {/* fine grain over the gradient — adds film-like texture */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.04] mix-blend-overlay"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)",
          backgroundSize: "12px 12px",
        }}
      />

      <div className="relative flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-indigo-600/80 dark:text-indigo-300/80">
        <span className="inline-block size-1.5 animate-pulse rounded-full bg-indigo-500 dark:bg-indigo-300" />
        {dateLabel}
      </div>

      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="relative mt-3 font-serif text-5xl font-medium tracking-tight text-slate-900 sm:text-6xl dark:text-white"
      >
        {greeting}
        <span className="bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-500 bg-clip-text text-transparent">
          .
        </span>
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="relative mt-3 max-w-xl text-base leading-relaxed text-slate-600 dark:text-slate-300"
      >
        {prompt}
      </motion.p>
    </motion.div>
  );
}
