"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Search,
  Settings,
  DollarSign,
  Gauge,
  Sun,
  Moon,
  LayoutDashboard,
  Compass,
  FlaskConical,
  Library,
  Bot,
  FileText,
  Sparkles,
} from "lucide-react";
import { useTheme } from "next-themes";
import { motion } from "framer-motion";
import { ModelStatusChip } from "@/components/brand/model-status-chip";
import { TokenBudgetChip } from "@/components/tokens/token-budget-chip";
import { LocaleSwitcher } from "@/components/brand/locale-switcher";
import { OfflineIndicator } from "@/components/brand/offline-indicator";
import { MobileNav } from "@/components/layout/mobile-nav";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useT } from "@/lib/i18n-provider";
import { cn } from "@/lib/utils";

/**
 * Sticky top header — Atlas brand on the left, primary nav tabs in the center,
 * status chips + utilities on the right. Replaces the old left sidebar.
 */
export function TopBar() {
  return (
    <header className="sticky top-0 z-30 border-b-2 border-slate-200/70 bg-white/85 backdrop-blur-xl shadow-sm dark:border-slate-800/80 dark:bg-slate-950/85">
      <div className="flex h-14 items-center gap-3 px-3 sm:px-5">
        <MobileNav />
        <Brand />
        <div className="hidden md:flex flex-1 items-center justify-center px-2">
          <PrimaryNav />
        </div>
        <div className="md:hidden flex-1" />
        <div className="flex items-center gap-1.5">
          <OfflineIndicator />
          <CommandPaletteHint />
          <div className="hidden lg:flex items-center gap-1.5">
            <ModelStatusChip />
            <TokenBudgetChip />
          </div>
          <div className="h-5 w-px bg-border mx-1" />
          <LocaleSwitcher />
          <ThemeToggle />
          <SettingsMenu />
        </div>
      </div>
    </header>
  );
}

function Brand() {
  return (
    <Link
      href="/"
      className="group flex items-center gap-2.5 shrink-0 transition-transform hover:scale-[1.02]"
    >
      <div className="relative flex size-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/30">
        <Sparkles className="size-4 drop-shadow" />
        <div className="absolute inset-0 rounded-xl ring-1 ring-white/30" />
      </div>
      <div className="hidden sm:flex flex-col leading-none">
        <span className="font-serif text-[15px] font-semibold tracking-tight text-slate-900 dark:text-white">
          Atlas
        </span>
        <span className="mt-1 text-[10px] font-medium text-slate-500 dark:text-slate-500">
          AI research partner
        </span>
      </div>
    </Link>
  );
}

interface TabItem {
  key: string;
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

function PrimaryNav() {
  const pathname = usePathname();
  const { t } = useT();

  const tabs: TabItem[] = [
    {
      key: "dashboard",
      label: t("nav.dashboard"),
      href: "/",
      icon: LayoutDashboard,
    },
    {
      key: "research",
      label: t("nav.research"),
      href: "/research",
      icon: FlaskConical,
    },
    {
      key: "discover",
      label: t("nav.discover"),
      href: "/discover",
      icon: Compass,
    },
    {
      key: "library",
      label: t("nav.library"),
      href: "/library",
      icon: Library,
    },
    {
      key: "reports",
      label: t("nav.reports"),
      href: "/reports",
      icon: FileText,
    },
    { key: "agents", label: t("nav.agents"), href: "/agents", icon: Bot },
  ];

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <nav className="flex items-center gap-0.5 rounded-xl border border-slate-200/70 bg-slate-50/80 p-1 shadow-inner dark:border-slate-800 dark:bg-slate-900/60">
      {tabs.map((tab) => {
        const active = isActive(tab.href);
        const Icon = tab.icon;
        return (
          <Link
            key={tab.key}
            href={tab.href}
            className={cn(
              "relative flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-all",
              active
                ? "text-indigo-700 dark:text-indigo-200"
                : "text-slate-600 hover:text-slate-900 hover:bg-white/70 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-800/70",
            )}
          >
            {active && (
              <motion.div
                layoutId="topnav-active"
                className="absolute inset-0 rounded-lg bg-gradient-to-br from-white via-white to-indigo-50 shadow-md ring-1 ring-indigo-200/70 dark:from-slate-800 dark:via-slate-800 dark:to-indigo-950/40 dark:ring-indigo-700/50"
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
              />
            )}
            <span className="relative flex items-center gap-1.5 whitespace-nowrap">
              <Icon
                className={cn(
                  "size-4 shrink-0",
                  active && "text-indigo-600 dark:text-indigo-300",
                )}
              />
              <span>{tab.label}</span>
            </span>
          </Link>
        );
      })}
    </nav>
  );
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <button
      type="button"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition hover:bg-muted hover:text-foreground"
      aria-label="Toggle theme"
    >
      {theme === "dark" ? (
        <Sun className="size-4" />
      ) : (
        <Moon className="size-4" />
      )}
    </button>
  );
}

function CommandPaletteHint() {
  const isMac =
    typeof navigator !== "undefined" &&
    /Mac|iPhone|iPad/i.test(navigator.platform || navigator.userAgent);

  const trigger = () => {
    if (typeof window === "undefined") return;
    const useMeta = isMac;
    window.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "k",
        ctrlKey: !useMeta,
        metaKey: useMeta,
        bubbles: true,
      }),
    );
  };
  return (
    <button
      type="button"
      onClick={trigger}
      aria-label="Open command palette"
      className="hidden md:inline-flex items-center gap-2 rounded-md border bg-muted/40 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      <Search className="size-3.5" />
      <span>跳转 / 搜索</span>
      <kbd
        suppressHydrationWarning
        className="ml-2 rounded border bg-background px-1.5 py-0.5 font-mono text-[10px]"
      >
        {isMac ? "⌘K" : "Ctrl K"}
      </kbd>
    </button>
  );
}

function SettingsMenu() {
  const { t } = useT();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            aria-label={t("nav.settings") || "Settings"}
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <Settings className="size-4" />
          </button>
        }
      />
      <DropdownMenuContent align="end" sideOffset={6}>
        <DropdownMenuItem render={<Link href="/settings" />}>
          <Gauge className="mr-2 size-4" />
          {t("nav.settings") || "Settings"}
        </DropdownMenuItem>
        <DropdownMenuItem render={<Link href="/budgets" />}>
          <DollarSign className="mr-2 size-4" />
          {t("nav.budgets") || "Budgets"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
