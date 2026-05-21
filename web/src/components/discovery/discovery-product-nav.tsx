"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Compass, Newspaper, Radar, Telescope, Waypoints } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/discovery", label: "总览", icon: Compass },
  { href: "/discovery/explore", label: "找方向", icon: Telescope },
  { href: "/discovery/track", label: "追方向", icon: Radar },
  { href: "/discovery/watchlists", label: "观察列表", icon: Waypoints },
  { href: "/discovery/digest", label: "周报归档", icon: Newspaper },
];

export function DiscoveryProductNav() {
  const pathname = usePathname() ?? "";

  return (
    <nav className="hidden items-center gap-2 lg:flex">
      {navItems.map((item) => {
        const Icon = item.icon;
        const active =
          pathname === item.href ||
          (item.href !== "/discovery" && pathname.startsWith(`${item.href}/`));

        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm transition",
              active
                ? "border-cyan-300/35 bg-cyan-300/12 text-cyan-50"
                : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:bg-white/[0.06] hover:text-white",
            )}
          >
            <Icon className="size-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
