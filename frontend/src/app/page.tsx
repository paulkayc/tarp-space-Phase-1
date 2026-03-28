import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-[calc(100vh-56px)] flex-col items-center justify-center px-6">
      <div className="mb-12 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-primary">
          tarpspace
        </h1>
        <p className="mt-2 font-mono text-sm text-muted">
          local marketplace · phase 1 poc
        </p>
      </div>

      <div className="grid w-full max-w-2xl gap-4 sm:grid-cols-2">
        <Link
          href="/personal-agent"
          className="group flex flex-col rounded-lg p-6 transition-colors"
          style={{
            background: "#141720",
            border: "1px solid #252836",
          }}
        >
          <span className="mb-0.5 font-mono text-[10px] tracking-[0.2em] text-muted">
            AGENT 01
          </span>
          <span className="mb-2 text-lg font-semibold text-primary">
            Personal Agent
          </span>
          <span className="text-sm leading-relaxed text-muted">
            Learns who you are — name, city, preferences, and communication
            style. Saves everything to long-term memory.
          </span>
          <span className="mt-5 self-start font-mono text-xs text-accent-blue group-hover:underline">
            open →
          </span>
        </Link>

        <Link
          href="/mandate-agent"
          className="group flex flex-col rounded-lg p-6 transition-colors"
          style={{
            background: "#141720",
            border: "1px solid #60a5fa",
          }}
        >
          <span className="mb-0.5 font-mono text-[10px] tracking-[0.2em] text-muted">
            AGENT 02
          </span>
          <span className="mb-2 text-lg font-semibold text-primary">
            Mandate Agent
          </span>
          <span className="text-sm leading-relaxed text-muted">
            Learns what you want right now — intent, category, budget,
            location, and conditions. Builds a structured mandate.
          </span>
          <span className="mt-5 self-start font-mono text-xs text-accent-blue group-hover:underline">
            open →
          </span>
        </Link>
      
        <Link
          href="/agent-builder"
          className="group flex flex-col rounded-lg p-6 transition-colors"
          style={{
            background: "#141720",
            border: "1px solid #34d399",
          }}
        >
          <span className="mb-0.5 font-mono text-[10px] tracking-[0.2em] text-muted">
            AGENT LAB
          </span>
          <span className="mb-2 text-lg font-semibold text-primary">
            Visual Agent Builder
          </span>
          <span className="text-sm leading-relaxed text-muted">
            Build agent graphs visually, attach tools and guardrails, validate, simulate, then generate and import runtime files.
          </span>
          <span className="mt-5 self-start font-mono text-xs text-emerald-300 group-hover:underline">
            open →
          </span>
        </Link>
      </div>
    </main>
  );
}
