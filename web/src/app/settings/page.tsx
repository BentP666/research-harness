"use client";

import Link from "next/link";
import { Settings, Scale, TrendingUp, KeyRound, Plug } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { useT } from "@/lib/i18n-provider";

export default function SettingsIndexPage() {
  const { t } = useT();

  const SECTIONS = [
    {
      href: "/settings/scoring",
      icon: Scale,
      title: t("settings.scoring.title"),
      description: t("settings.scoring.description"),
    },
    {
      href: "/research/trends",
      icon: TrendingUp,
      title: t("settings.trends.title"),
      description: t("settings.trends.description"),
    },
    {
      href: "/agents",
      icon: KeyRound,
      title: t("settings.agentsKeys.title"),
      description: t("settings.agentsKeys.description"),
    },
    {
      href: "/settings/providers",
      icon: Plug,
      title: t("settings.providers.title"),
      description: t("settings.providers.description"),
    },
  ];

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Settings className="size-5" />
          {t("settings.title")}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("settings.subtitle")}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {SECTIONS.map((s) => (
          <Link key={s.href} href={s.href}>
            <Card className="hover:border-foreground/20 transition-colors">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <s.icon className="size-4" />
                  {s.title}
                </CardTitle>
                <CardDescription>{s.description}</CardDescription>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground">
                {s.href} →
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
