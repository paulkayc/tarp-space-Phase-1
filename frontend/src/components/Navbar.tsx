"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Navbar() {
  const pathname = usePathname();
  const isMandateActive = pathname === "/mandate-agent";
  const isPersonalActive = pathname === "/personal-agent";
  const isBuilderActive = pathname === "/agent-builder";

  return (
    <nav
      className="fixed inset-x-0 top-0 z-50 flex h-14 items-center justify-between px-6"
      style={{ background: "#0d0f14", borderBottom: "1px solid #1e2235" }}
    >
      {/* Logo */}
      <Link href="/" className="flex items-baseline gap-1.5">
        <span className="text-lg font-bold tracking-tight text-primary">
          tarpspace
        </span>
        <span className="font-mono text-xs text-muted">poc</span>
      </Link>

      {/* Agent switcher */}
      <div className="flex items-center gap-4">
        <Link
          href="/personal-agent"
          className={[
            "font-mono text-sm tracking-wide transition-colors",
            isPersonalActive
              ? "text-accent-blue"
              : "text-muted hover:text-primary",
          ].join(" ")}
        >
          personal agent
        </Link>

        <Link
          href="/mandate-agent"
          className={[
            "rounded border px-4 py-1.5 font-mono text-sm tracking-wide transition-colors",
            isMandateActive
              ? "border-accent-blue text-accent-blue"
              : "border-border-dark text-muted hover:border-muted hover:text-primary",
          ].join(" ")}
        >
          mandate agent
        </Link>
              <Link
          href="/agent-builder"
          className={[
            "rounded border px-4 py-1.5 font-mono text-sm tracking-wide transition-colors",
            isBuilderActive
              ? "border-emerald-400 text-emerald-300"
              : "border-border-dark text-muted hover:border-muted hover:text-primary",
          ].join(" ")}
        >
          agent builder
        </Link>
      </div>
    </nav>
  );
}
