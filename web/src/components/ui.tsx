"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import type { Job, Platform } from "@/lib/api";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 2000 } } }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const NAV = [
  { href: "/", label: "Inbox" },
  { href: "/library", label: "Library" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const path = usePathname();
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href) || (href === "/library" && path.startsWith("/t/")));
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex h-12 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-serif text-[17px] font-medium tracking-tight">
          <span aria-hidden className="h-2 w-2 rounded-full bg-accent" />
          Transcript Desk
        </Link>
        <nav className="flex h-full items-stretch gap-1">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              aria-current={active(n.href) ? "page" : undefined}
              className={`flex items-center border-b-2 px-2.5 text-[13px] ${
                active(n.href) ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink"
              }`}
            >
              {n.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}

const PLATFORM: Record<Platform, { label: string; color: string }> = {
  tiktok: { label: "TikTok", color: "var(--tiktok)" },
  instagram: { label: "Instagram", color: "var(--instagram)" },
  youtube: { label: "YouTube", color: "var(--youtube)" },
};

export function PlatformMark({ platform, showLabel = false }: { platform: Platform | null; showLabel?: boolean }) {
  const p = platform ? PLATFORM[platform] : { label: "Unknown", color: "var(--muted)" };
  return (
    <span className="inline-flex items-center gap-1.5 text-muted" title={p.label}>
      <span aria-hidden className="h-2 w-2 shrink-0 rounded-full" style={{ background: p.color }} />
      {showLabel ? <span className="text-[12px]">{p.label}</span> : <span className="sr-only">{p.label}</span>}
    </span>
  );
}

const STATUS_TEXT: Record<Job["status"], string> = {
  queued: "Queued", resolving: "Resolving link", fetching: "Fetching captions",
  transcribing: "Transcribing audio", done: "Done", failed: "Failed",
};

export function StatusPill({ job }: { job: Job }) {
  if (job.status === "done") return <span className="label !text-ok">Done</span>;
  if (job.status === "failed") return <span className="label !text-bad">{job.error_code?.replaceAll("_", " ") ?? "Failed"}</span>;
  return (
    <span className="label inline-flex items-center gap-1.5 !text-ink">
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full bg-accent ${job.status === "queued" ? "opacity-40" : "rec"}`} />
      {STATUS_TEXT[job.status]}
    </span>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="border border-dashed border-line px-6 py-12 text-center">
      <p className="font-serif text-[19px]">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-[13px] leading-relaxed text-muted">{children}</div>}
    </div>
  );
}

export function CopyButton({ text, label = "Copy", className = "btn" }: { text: string; label?: string; className?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className={className}
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1400);
      }}
    >
      {done ? "Copied" : label}
    </button>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="border-l-2 border-bad bg-surface px-3 py-2 text-[13px] text-bad">
      {error instanceof Error ? error.message : "Something went wrong."} Is the api service running?
    </p>
  );
}
