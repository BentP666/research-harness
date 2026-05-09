"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Compass,
  FlaskConical,
  Library,
  PanelLeftClose,
  PanelLeftOpen,
  Sun,
  Moon,
  Bot,
  FileText,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { useTheme } from "next-themes";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n-provider";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface NavItem {
  key: string;
  label: string;
  hint: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavGroup {
  heading: string;
  items: NavItem[];
}

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { theme, setTheme } = useTheme();
  const { t } = useT();

  const GROUPS: NavGroup[] = [
    {
      heading: t("sidebar.todayGroup") || "TODAY",
      items: [
        {
          key: "dashboard",
          label: t("nav.dashboard"),
          hint: "Today's recommended next steps",
          href: "/",
          icon: LayoutDashboard,
        },
      ],
    },
    {
      heading: t("sidebar.researchGroup") || "RESEARCH",
      items: [
        {
          key: "research",
          label: t("nav.research"),
          hint: "All your research projects",
          href: "/research",
          icon: FlaskConical,
        },
        {
          key: "discover",
          label: t("nav.discover"),
          hint: "What the field is doing",
          href: "/discover",
          icon: Compass,
        },
      ],
    },
    {
      heading: t("sidebar.knowledgeGroup") || "KNOWLEDGE",
      items: [
        {
          key: "library",
          label: t("nav.library"),
          hint: "Every paper you've collected",
          href: "/library",
          icon: Library,
        },
        {
          key: "reports",
          label: t("nav.reports"),
          hint: "Drafts and exports",
          href: "/reports",
          icon: FileText,
        },
      ],
    },
    {
      heading: t("sidebar.systemGroup") || "SYSTEM",
      items: [
        {
          key: "agents",
          label: t("nav.agents"),
          hint: "Connected AI models",
          href: "/agents",
          icon: Bot,
        },
      ],
    },
  ];

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <aside
      className={cn(
        // Glass aesthetic — light + translucent in light mode, deep slate in dark.
        "hidden md:flex h-full flex-col border-r transition-[width] duration-300",
        "border-slate-200/70 bg-white/70 text-slate-700 backdrop-blur-xl",
        "dark:border-slate-800/80 dark:bg-slate-950/60 dark:text-slate-300",
        collapsed ? "w-16" : "w-56",
      )}
    >
      {/* Branding — gradient logo, refined typography */}
      <Link
        href="/"
        className="group relative flex h-14 items-center gap-2.5 border-b border-slate-200/70 px-4 transition-colors hover:bg-slate-100/60 dark:border-slate-800/80 dark:hover:bg-slate-900/60"
      >
        <div className="relative flex size-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/20 transition-transform group-hover:scale-105">
          <Sparkles className="size-4" />
          {/* subtle ring */}
          <div className="absolute inset-0 rounded-xl ring-1 ring-white/20" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="truncate font-serif text-[15px] font-semibold tracking-tight text-slate-900 dark:text-white">
              Atlas
            </div>
            <div className="truncate text-[10px] font-medium text-slate-500 dark:text-slate-500">
              AI research partner
            </div>
          </div>
        )}
      </Link>

      {/* Navigation — grouped with category headings */}
      <nav className="flex flex-1 flex-col gap-4 overflow-y-auto px-2 py-4">
        {GROUPS.map((group) => (
          <div key={group.heading} className="flex flex-col gap-0.5">
            {!collapsed && (
              <div className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500">
                {group.heading}
              </div>
            )}
            {group.items.map((item) => {
              const active = isActive(item.href);
              const linkEl = (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "group/item relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all",
                    active
                      ? "bg-gradient-to-r from-indigo-500/10 via-violet-500/5 to-transparent text-indigo-700 dark:from-indigo-400/15 dark:text-indigo-200"
                      : "text-slate-600 hover:bg-slate-100/80 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/50 dark:hover:text-slate-100",
                  )}
                >
                  {/* Active indicator: left vertical gradient bar */}
                  {active && (
                    <motion.div
                      layoutId="sidebar-active-indicator"
                      className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-gradient-to-b from-indigo-500 to-violet-500"
                      transition={{ type: "spring", stiffness: 400, damping: 30 }}
                    />
                  )}
                  <item.icon
                    className={cn(
                      "size-[17px] shrink-0 transition-transform group-hover/item:scale-110",
                      active && "text-indigo-600 dark:text-indigo-300",
                    )}
                  />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              );
              return (
                <Tooltip key={item.key}>
                  <TooltipTrigger render={linkEl} />
                  <TooltipContent side="right" className="text-xs">
                    <div className="font-semibold">{item.label}</div>
                    <div className="mt-0.5 text-[11px] opacity-80">
                      {item.hint}
                    </div>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer — theme + collapse */}
      <div className="border-t border-slate-200/70 px-2 py-2 space-y-1 dark:border-slate-800/80">
        <button
          type="button"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="flex w-full items-center justify-center rounded-lg p-2 text-slate-500 transition-all hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          title={theme === "dark" ? "Light mode" : "Dark mode"}
        >
          {theme === "dark" ? (
            <Sun className="size-4" />
          ) : (
            <Moon className="size-4" />
          )}
        </button>
        <button
          type="button"
          onClick={() => setCollapsed((prev) => !prev)}
          className="flex w-full items-center justify-center rounded-lg p-2 text-slate-500 transition-all hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeftOpen className="size-4" />
          ) : (
            <PanelLeftClose className="size-4" />
          )}
        </button>
      </div>
    </aside>
  );
}
