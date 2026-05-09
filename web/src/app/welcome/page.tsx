"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Sparkles, ArrowRight, Search, Target, PenSquare, Cpu } from "lucide-react";
import { useT } from "@/lib/i18n-provider";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function WelcomePage() {
  const { t } = useT();

  const pillars = [
    {
      icon: Search,
      title: t("welcome.pillars.gather.title"),
      body: t("welcome.pillars.gather.body"),
      accent: "from-sky-400/20 to-sky-600/10",
    },
    {
      icon: Target,
      title: t("welcome.pillars.analyze.title"),
      body: t("welcome.pillars.analyze.body"),
      accent: "from-emerald-400/20 to-emerald-600/10",
    },
    {
      icon: PenSquare,
      title: t("welcome.pillars.write.title"),
      body: t("welcome.pillars.write.body"),
      accent: "from-indigo-400/20 to-indigo-600/10",
    },
  ];

  return (
    <div className="relative mx-auto flex min-h-[80vh] max-w-5xl flex-col items-center justify-center px-6 py-16">
      {/* Backdrop */}
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-96 bg-gradient-to-b from-indigo-100/40 via-transparent to-transparent dark:from-indigo-950/30" />
        <div className="absolute left-1/2 top-20 -z-10 h-64 w-64 -translate-x-1/2 rounded-full bg-indigo-300/20 blur-3xl dark:bg-indigo-700/10" />
      </div>

      {/* Brand */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="flex items-center gap-2 text-sm font-medium text-muted-foreground"
      >
        <Sparkles className="size-3.5" />
        {t("brand.poweredBy")}
      </motion.div>

      {/* Hero */}
      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.05, ease: "easeOut" }}
        className="mt-3 text-center font-serif text-5xl font-medium leading-tight tracking-tight sm:text-6xl"
      >
        {t("welcome.title")}
      </motion.h1>
      <motion.p
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.12, ease: "easeOut" }}
        className="mt-4 max-w-xl text-center text-base text-muted-foreground sm:text-lg"
      >
        {t("welcome.subtitle")}
      </motion.p>

      {/* Pillars */}
      <div className="mt-12 grid w-full gap-4 sm:grid-cols-3">
        {pillars.map((p, i) => (
          <motion.div
            key={p.title}
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.25 + i * 0.08, ease: "easeOut" }}
          >
            <Card className="relative h-full overflow-hidden border-0 bg-gradient-to-br p-6 shadow-sm ring-1 ring-black/5 dark:ring-white/5">
              <div
                className={`absolute inset-0 bg-gradient-to-br ${p.accent}`}
              />
              <div className="relative space-y-3">
                <div className="flex size-10 items-center justify-center rounded-xl bg-background/80 ring-1 ring-black/5 dark:ring-white/10">
                  <p.icon className="size-5" />
                </div>
                <h3 className="font-serif text-lg font-semibold tracking-tight">
                  {p.title}
                </h3>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {p.body}
                </p>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* CTAs */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.55, ease: "easeOut" }}
        className="mt-12 flex flex-col items-center gap-3 sm:flex-row"
      >
        <Button size="lg" className="gap-2" render={<Link href="/topics/new" />}>
          <Sparkles className="size-4" />
          {t("welcome.cta.startBlank")}
          <ArrowRight className="size-4" />
        </Button>
        <Button
          size="lg"
          variant="outline"
          className="gap-2"
          render={<Link href="/agents?new=1" />}
        >
          <Cpu className="size-4" />
          {t("welcome.cta.configureModel")}
        </Button>
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.7 }}
        transition={{ duration: 0.5, delay: 0.7 }}
        className="mt-8 max-w-md text-center text-xs text-muted-foreground"
      >
        No API key yet? You can explore with a local demo engine — the core
        workflow still works. Connect a real model later when you want to run
        on your own research.
      </motion.p>
    </div>
  );
}
