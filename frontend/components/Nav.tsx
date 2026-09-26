"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  CohortsIcon,
  CustomersIcon,
  ModelsIcon,
  MonitoringIcon,
  OverviewIcon,
  SegmentsIcon,
  SimulatorIcon,
} from "@/components/icons";

const LINKS: { href: string; label: string; icon: ReactNode }[] = [
  { href: "/", label: "Overview", icon: <OverviewIcon /> },
  { href: "/customers", label: "Customers", icon: <CustomersIcon /> },
  { href: "/segments", label: "Segments", icon: <SegmentsIcon /> },
  { href: "/cohorts", label: "Cohorts", icon: <CohortsIcon /> },
  { href: "/model-center", label: "Model Center", icon: <ModelsIcon /> },
  { href: "/retention-simulator", label: "Retention Simulator", icon: <SimulatorIcon /> },
  { href: "/monitoring", label: "Monitoring", icon: <MonitoringIcon /> },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-white/10">
        <svg viewBox="0 0 32 32" width="20" height="20" aria-hidden="true">
          <rect x="6" y="18" width="5" height="8" rx="1.2" fill="#7fc4a3" />
          <rect x="13.5" y="12" width="5" height="14" rx="1.2" fill="#e0c36a" />
          <rect x="21" y="6" width="5" height="20" rx="1.2" fill="#e8785f" />
        </svg>
      </span>
      <span className="text-[15px] font-semibold leading-tight tracking-tight text-white">
        Customer
        <br />
        Intelligence
      </span>
    </Link>
  );
}

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1" aria-label="Main">
      {LINKS.map((link) => {
        const active = isActive(pathname, link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
              active ? "bg-white/10 text-white" : "text-sidebar-ink hover:bg-white/5 hover:text-white"
            }`}
          >
            <span className={active ? "text-[#7fc4a3]" : ""}>{link.icon}</span>
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

const FOOTNOTE = "Synthetic data. Scores are batch-computed and read from the database.";

export default function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);

  // While the drawer is open: Escape closes it, the page behind does not
  // scroll, and focus moves into the drawer (and back to the menu button on close).
  useEffect(() => {
    if (!open) return;
    const button = menuButton.current;
    // The drawer is still `visibility: hidden` on the first frame of the
    // slide-in, and hidden elements cannot take focus, so wait a beat.
    const focusTimer = window.setTimeout(() => closeButton.current?.focus(), 60);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(focusTimer);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKey);
      button?.focus();
    };
  }, [open]);

  return (
    <>
      {/* Desktop: fixed sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col bg-sidebar px-4 py-5 lg:flex">
        <div className="px-2">
          <Brand />
        </div>
        <div className="mt-8">
          <NavLinks pathname={pathname} />
        </div>
        <p className="mt-auto px-2 text-xs leading-relaxed text-sidebar-ink/70">{FOOTNOTE}</p>
      </aside>

      {/* Phone and tablet: top bar with a menu button */}
      <header className="sticky top-0 z-30 flex items-center justify-between bg-sidebar px-4 py-3 lg:hidden">
        <Brand />
        <button
          ref={menuButton}
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open menu"
          aria-expanded={open}
          aria-controls="mobile-menu"
          className="grid h-10 w-10 place-items-center rounded-lg text-white hover:bg-white/10"
        >
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
      </header>

      {/* Backdrop */}
      <div
        onClick={() => setOpen(false)}
        aria-hidden="true"
        className={`fixed inset-0 z-40 bg-black/50 transition-opacity duration-200 lg:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      {/* Slide-in drawer */}
      <aside
        id="mobile-menu"
        aria-label="Menu"
        className={`fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col bg-sidebar px-4 py-5 shadow-2xl transition-[transform,visibility] duration-200 ease-out lg:hidden ${
          open ? "visible translate-x-0" : "invisible -translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-2">
          <Brand />
          <button
            ref={closeButton}
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close menu"
            className="grid h-10 w-10 place-items-center rounded-lg text-sidebar-ink hover:bg-white/10 hover:text-white"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
        <div className="mt-8 overflow-y-auto">
          <NavLinks pathname={pathname} onNavigate={() => setOpen(false)} />
        </div>
        <p className="mt-auto px-2 pt-6 text-xs leading-relaxed text-sidebar-ink/70">{FOOTNOTE}</p>
      </aside>
    </>
  );
}
