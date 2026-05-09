"use client";

import { Globe } from "lucide-react";
import { useT } from "@/lib/i18n-provider";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Locale } from "@/lib/glossary";

const LANGS: Array<{ code: Locale; label: string }> = [
  { code: "en", label: "English" },
  { code: "zh", label: "中文" },
];

export function LocaleSwitcher() {
  const { locale, setLocale } = useT();
  const current = LANGS.find((l) => l.code === locale) ?? LANGS[0];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            title="Language / 语言"
          >
            <Globe className="size-3.5" />
            <span className="font-medium">{current.label}</span>
          </Button>
        }
      />
      <DropdownMenuContent align="end">
        {LANGS.map((lang) => (
          <DropdownMenuItem
            key={lang.code}
            onClick={() => setLocale(lang.code)}
            className={lang.code === locale ? "font-semibold" : ""}
          >
            {lang.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
