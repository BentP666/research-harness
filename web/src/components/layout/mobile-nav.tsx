"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Compass,
  FlaskConical,
  Library,
  Menu,
  Bot,
  FileText,
  Sparkles,
  TrendingUp,
  Settings,
  X,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n-provider";
import { cn } from "@/lib/utils";
import { useState } from "react";

export function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { t } = useT();

  const primaryItems = [
    { key: "dashboard", label: t("nav.dashboard"), href: "/", icon: LayoutDashboard },
    { key: "research", label: t("nav.research"), href: "/research", icon: FlaskConical },
    { key: "library", label: t("nav.library"), href: "/library", icon: Library },
    { key: "reports", label: t("nav.reports"), href: "/reports", icon: FileText },
  ];

  const labItems = [
    { key: "trends", label: t("nav.trends"), href: "/research/trends", icon: TrendingUp },
    { key: "discover", label: t("nav.discover"), href: "/discover", icon: Compass },
    { key: "agents", label: t("nav.agents"), href: "/agents", icon: Bot },
    { key: "settings", label: t("nav.settings"), href: "/settings", icon: Settings },
  ];

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <Button
            variant="ghost"
            size="sm"
            className="md:hidden gap-1.5"
            aria-label="Menu"
          >
            <Menu className="size-4" />
          </Button>
        }
      />
      <SheetContent side="left" className="w-72 p-0">
        <div className="flex h-full flex-col bg-slate-950 text-slate-300">
          <div className="flex h-14 items-center justify-between border-b border-slate-800 px-4">
            <Link
              href="/"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2"
            >
              <div className="flex size-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700 text-white">
                <Sparkles className="size-4" />
              </div>
              <div>
                <div className="text-sm font-semibold text-white font-serif">
                  Research Harness
                </div>
                <div className="text-[10px] text-slate-500">
                  AI research workbench
                </div>
              </div>
            </Link>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-md p-1 text-slate-500 hover:bg-slate-800 hover:text-slate-300"
              aria-label="Close"
            >
              <X className="size-4" />
            </button>
          </div>
          <nav className="flex flex-1 flex-col gap-1 p-2">
            {primaryItems.map((item) => {
              const active = isActive(item.href);
              return (
                <Link
                  key={item.key}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-slate-800 text-white"
                      : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                  )}
                >
                  <item.icon className="size-4 shrink-0" />
                  <span>{item.label}</span>
                </Link>
              );
            })}

            <div className="mt-4 border-t border-slate-800 pt-3">
              <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">
                {t("nav.labs")}
              </p>
              {labItems.map((item) => {
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.key}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      active
                        ? "bg-slate-800 text-white"
                        : "text-slate-500 hover:bg-slate-800/60 hover:text-slate-300"
                    )}
                  >
                    <item.icon className="size-4 shrink-0" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </nav>
        </div>
      </SheetContent>
    </Sheet>
  );
}
