"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { MyntraMark } from "@/components/MyntraMark";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/?tab=questions", label: "Questions" },
  { href: "/?tab=bets", label: "Topics" },
  { href: "/compare", label: "Compare reasons" },
  { href: "/health", label: "Data sources" },
];

export function AppHeader() {
  const pathname = usePathname();
  const params = useSearchParams();
  const tab = params.get("tab");
  const router = useRouter();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);

  function submitSearch(e: React.FormEvent) {
    e.preventDefault();
    const query = q.trim();
    router.push(query ? `/?tab=bets&q=${encodeURIComponent(query)}` : "/?tab=bets");
    setOpen(false);
  }

  return (
    <header className="sticky top-0 z-40 border-b border-myntra-line bg-white shadow-card">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
        <Link href="/" className="flex shrink-0 items-center gap-3">
          <MyntraMark />
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-myntra-pink">
            Wishlist insights
          </span>
        </Link>
        <form onSubmit={submitSearch} className="hidden min-w-0 flex-1 md:block">
          <label className="sr-only" htmlFor="dash-search">
            Search topics
          </label>
          <input
            id="dash-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search fit, sale, returns…"
            className="w-full rounded-sm bg-myntra-wash px-4 py-2.5 text-sm text-myntra-ink placeholder:text-myntra-muted"
          />
        </form>
        <button
          type="button"
          className="ml-auto rounded-sm border border-myntra-line px-3 py-2 text-xs font-bold uppercase tracking-wide md:hidden"
          onClick={() => setOpen((v) => !v)}
        >
          Menu
        </button>
      </div>
      <nav className="hidden border-t border-myntra-line md:block">
        <div className="mx-auto flex max-w-7xl gap-6 px-4">
          {NAV.map((item) => {
            const active = isActive(item.href, pathname, tab);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`border-b-4 py-3 text-sm font-bold uppercase tracking-wide ${
                  active ? "border-myntra-pink text-myntra-ink" : "border-transparent text-myntra-muted hover:text-myntra-ink"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
      {open ? (
        <div className="space-y-2 border-t border-myntra-line bg-white px-4 py-3 md:hidden">
          <form onSubmit={submitSearch}>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search fit, sale, returns…"
              className="mb-2 w-full rounded-sm bg-myntra-wash px-3 py-2 text-sm"
            />
          </form>
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block py-2 text-sm font-semibold uppercase text-myntra-ink"
              onClick={() => setOpen(false)}
            >
              {item.label}
            </Link>
          ))}
        </div>
      ) : null}
    </header>
  );
}

function isActive(href: string, pathname: string, tab: string | null) {
  if (href === "/compare") return pathname === "/compare";
  if (href === "/health") return pathname === "/health";
  if (href === "/?tab=questions") return pathname === "/" && tab === "questions";
  if (href === "/?tab=bets") return pathname === "/" && tab === "bets";
  if (href === "/") return pathname === "/" && tab !== "questions" && tab !== "bets";
  return false;
}
