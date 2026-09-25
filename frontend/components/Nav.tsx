"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
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

export default function Nav() {
  const pathname = usePathname();

  return (
    <>
      {/* Desktop: fixed sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col bg-sidebar px-4 py-5 lg:flex">
        <div className="px-2">
          <Brand />
        </div>
        <nav className="mt-8 flex flex-col gap-1" aria-label="Main">
          {LINKS.map((link) => {
            const active = isActive(pathname, link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  active ? "bg-white/10 text-white" : "text-sidebar-ink hover:bg-white/5 hover:text-white"
                }`}
              >
                <span className={active ? "text-[#7fc4a3]" : ""}>{link.icon}</span>
                {link.label}
              </Link>
            );
          })}
        </nav>
        <p className="mt-auto px-2 text-xs leading-relaxed text-sidebar-ink/70">
          Synthetic data. Scores are batch-computed and read from the database.
        </p>
      </aside>

      {/* Mobile and tablet: top bar with scrollable links */}
      <header className="sticky top-0 z-20 bg-sidebar lg:hidden">
        <div className="flex items-center px-4 py-3">
          <Brand />
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3" aria-label="Main">
          {LINKS.map((link) => {
            const active = isActive(pathname, link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium ${
                  active ? "bg-white/10 text-white" : "text-sidebar-ink"
                }`}
              >
                {link.icon}
                {link.label}
              </Link>
            );
          })}
        </nav>
      </header>
    </>
  );
}
