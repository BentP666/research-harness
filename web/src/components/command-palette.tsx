"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Command,
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import {
  Compass,
  FlaskConical,
  Library,
  FileText,
  Cpu,
  Settings,
  TrendingUp,
  Home,
  Plus,
  Telescope,
} from "lucide-react";
import { fetchTopics, fetchPapers } from "@/lib/api";

const NAV_ITEMS = [
  { label: "今日概览 / Dashboard", href: "/", icon: Home },
  { label: "研究中心 / Research", href: "/research", icon: FlaskConical },
  { label: "学术发现 / Discover", href: "/discover", icon: Telescope },
  { label: "趋势 / Trends", href: "/research/trends", icon: TrendingUp },
  { label: "文献资料 / Library", href: "/library", icon: Library },
  { label: "研究汇报 / Reports", href: "/reports", icon: FileText },
  { label: "模型配置 / Models", href: "/agents", icon: Cpu },
  { label: "系统设置 / Settings", href: "/settings", icon: Settings },
];

const ACTION_ITEMS = [
  { label: "新建 topic / Create new topic", href: "/topics/new", icon: Plus },
  { label: "新建 domain / Create new domain", href: "/domains/new", icon: Plus },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  // Global Cmd/Ctrl+K listener
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Lazy-load topics + papers only when palette is open
  const topicsQ = useQuery({
    queryKey: ["palette-topics"],
    queryFn: () => fetchTopics({}),
    enabled: open,
    staleTime: 60_000,
  });

  const papersQ = useQuery({
    queryKey: ["palette-papers"],
    queryFn: () => fetchPapers({ page: 1, page_size: 30 }),
    enabled: open,
    staleTime: 60_000,
  });

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="Command palette">
      <Command>
        <CommandInput placeholder="跳转到 topic、paper、报告… 或输入命令" />
        <CommandList>
        <CommandEmpty>没有匹配项。</CommandEmpty>

        <CommandGroup heading="Navigation">
          {NAV_ITEMS.map((it) => (
            <CommandItem
              key={it.href}
              value={`nav ${it.label}`}
              onSelect={() => go(it.href)}
            >
              <it.icon className="size-4 shrink-0" />
              <span>{it.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Actions">
          {ACTION_ITEMS.map((it) => (
            <CommandItem
              key={it.href}
              value={`action ${it.label}`}
              onSelect={() => go(it.href)}
            >
              <it.icon className="size-4 shrink-0" />
              <span>{it.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        {topicsQ.data?.length ? (
          <>
            <CommandSeparator />
            <CommandGroup heading="Topics">
              {topicsQ.data.slice(0, 30).map((tp) => (
                <CommandItem
                  key={`t-${tp.id}`}
                  value={`topic ${tp.name} ${tp.description ?? ""}`}
                  onSelect={() => go(`/topics/${tp.id}`)}
                >
                  <Compass className="size-4 shrink-0 opacity-60" />
                  <span className="truncate">{tp.name}</span>
                  {tp.current_stage ? (
                    <CommandShortcut>{tp.current_stage}</CommandShortcut>
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        ) : null}

        {papersQ.data?.items?.length ? (
          <>
            <CommandSeparator />
            <CommandGroup heading="Recent papers">
              {papersQ.data.items.slice(0, 20).map((p) => (
                <CommandItem
                  key={`p-${p.id}`}
                  value={`paper ${p.title}`}
                  onSelect={() => go(`/papers/${p.id}`)}
                >
                  <FileText className="size-4 shrink-0 opacity-60" />
                  <span className="truncate">{p.title}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        ) : null}
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
