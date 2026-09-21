import Link from "next/link";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/customers", label: "Customers" },
  { href: "/segments", label: "Segments" },
  { href: "/cohorts", label: "Cohorts" },
  { href: "/model-center", label: "Model Center" },
  { href: "/retention-simulator", label: "Retention Simulator" },
  { href: "/monitoring", label: "Monitoring" },
];

export default function Nav() {
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-6xl items-center gap-8 px-6 py-4">
        <Link href="/" className="text-lg font-medium tracking-tight text-ink">
          Customer Intelligence
        </Link>
        <nav className="flex flex-wrap gap-5 text-sm text-ink-soft">
          {LINKS.map((link) => (
            <Link key={link.href} href={link.href} className="hover:text-ink transition-colors">
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
