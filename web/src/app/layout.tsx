import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";
import { TopBar } from "@/components/layout/top-bar";
import { CommandPalette } from "@/components/command-palette";
import { BackgroundTasksTray } from "@/components/tasks/background-tasks-tray";
import { QueryProvider } from "@/lib/query-provider";
import { ThemeProvider } from "@/lib/theme-provider";
import { I18nProvider } from "@/lib/i18n-provider";

export const metadata: Metadata = {
  title: "Atlas — Your AI research partner",
  description:
    "Discover papers that matter, spot research gaps, and draft with evidence.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
      suppressHydrationWarning
    >
      <body className="relative flex h-full min-h-dvh flex-col overflow-hidden bg-gradient-to-br from-slate-50 via-white to-indigo-50/30 text-foreground dark:from-slate-950 dark:via-slate-950 dark:to-indigo-950/20">
        {/* Ambient mesh — soft orbs that drift the eye around the page */}
        <div
          aria-hidden
          className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
        >
          <div className="absolute -left-32 top-20 size-[420px] rounded-full bg-indigo-300/15 blur-3xl dark:bg-indigo-600/10" />
          <div className="absolute right-[-10%] top-[30%] size-[520px] rounded-full bg-violet-300/10 blur-3xl dark:bg-violet-700/10" />
          <div className="absolute bottom-[-10%] left-1/3 size-[460px] rounded-full bg-amber-200/15 blur-3xl dark:bg-amber-700/10" />
        </div>

        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <I18nProvider>
            <QueryProvider>
              <TopBar />
              <main className="relative flex flex-1 flex-col overflow-y-auto">
                <div className="flex-1">{children}</div>
              </main>
              <CommandPalette />
              <BackgroundTasksTray />
              <Toaster
                position="bottom-right"
                toastOptions={{
                  classNames: {
                    toast:
                      "rounded-lg border bg-background text-foreground shadow-lg",
                  },
                }}
              />
            </QueryProvider>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
