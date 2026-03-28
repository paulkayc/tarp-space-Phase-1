"use client";

import {
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  createMandateAgentSession,
  FlatMandateState,
  MandateState,
  sendMandateAgentMessage,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ChatMessage = {
  role: "user" | "agent";
  content: string;
};

type BadgeKind = "explicit" | "inferred" | "none";

// ---------------------------------------------------------------------------
// Markdown renderer (no external lib)
// Bold **text**, em *text*, bullet lines starting with – or *, newlines → <br>
// ---------------------------------------------------------------------------

function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split("\n");
  return lines.map((line, li) => {
    // Bold + italic inline patterns
    const parts = line.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    const inline = parts.map((part, pi) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={pi}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={pi}>{part.slice(1, -1)}</em>;
      }
      return <span key={pi}>{part}</span>;
    });
    return (
      <span key={li}>
        {inline}
        {li < lines.length - 1 && <br />}
      </span>
    );
  });
}

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------

function Badge({ kind }: { kind: BadgeKind }) {
  if (kind === "none") return null;
  const cls =
    kind === "explicit"
      ? "border border-green-800 text-accent-green"
      : "border border-yellow-800 text-accent-orange";
  return (
    <span
      className={`shrink-0 rounded px-2 py-0.5 font-mono text-[10px] tracking-widest ${cls}`}
    >
      {kind}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Field row
// ---------------------------------------------------------------------------

function FieldRow({
  label,
  value,
  badge,
  mono = false,
}: {
  label: string;
  value: string | null | undefined;
  badge: BadgeKind;
  mono?: boolean;
}) {
  const empty = !value;
  return (
    <div className="flex items-center gap-3 py-2.5">
      <span className="w-28 shrink-0 font-mono text-xs text-muted">
        {label}
      </span>
      <span
        className={[
          "min-w-0 flex-1 text-sm",
          empty ? "text-dim" : "text-primary",
          mono ? "font-mono" : "",
        ].join(" ")}
      >
        {empty ? "—" : mono ? (
          <span className="rounded bg-surface px-1.5 py-0.5">{value}</span>
        ) : value}
      </span>
      <Badge kind={empty ? "none" : badge} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section header
// ---------------------------------------------------------------------------

function SectionHeader({ label }: { label: string }) {
  return (
    <p className="mb-1 mt-4 font-mono text-[10px] tracking-[0.2em] text-muted first:mt-0">
      {label}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Flat-state helpers: build FlatMandateState from ORM MandateState on init
// ---------------------------------------------------------------------------

function ormToFlat(m: MandateState): FlatMandateState {
  const price = m.negotiation_range?.find((r) => r.dimension === "price");
  const budget = price
    ? { min: price.min, max: price.max }
    : undefined;
  return {
    intent_type: m.intent_type ?? undefined,
    vertical: m.vertical ?? undefined,
    category: m.category ?? undefined,
    budget,
    location: m.hard_constraints?.find((c) => c.field === "location")?.value,
    condition: m.hard_constraints?.find((c) => c.field === "condition")?.value,
    timing: m.hard_constraints?.find((c) => c.field === "timing")?.value,
    style_preferences: m.soft_preferences
      ?.filter((p) => p.field === "style")
      .map((p) => p.value),
    dealbreakers: m.dealbreakers ?? [],
    autonomy_level: m.autonomy_level,
  };
}

function formatBudget(b?: { min?: number; max?: number }): string | null {
  if (!b) return null;
  if (b.min != null && b.max != null) return `$${b.min}–$${b.max}`;
  if (b.max != null) return `$${b.max}`;
  if (b.min != null) return `at least $${b.min}`;
  return null;
}

// ---------------------------------------------------------------------------
// Live Mandate Panel
// ---------------------------------------------------------------------------

const THRESHOLD = 0.7;
const DEFAULT_AUTONOMY = "escalate_key_points";

function LiveMandatePanel({
  flat,
  completeness,
  delta,
  profileLoaded,
}: {
  flat: FlatMandateState | null;
  completeness: number;
  delta: Record<string, unknown>;
  profileLoaded: boolean;
}) {
  const pct = Math.round(completeness * 100);
  const ready = completeness >= THRESHOLD;

  function badge(fieldKey: string): BadgeKind {
    if (!flat) return "none";
    const val = (flat as Record<string, unknown>)[fieldKey];
    if (val === undefined || val === null || val === "" || (Array.isArray(val) && val.length === 0)) return "none";
    if (fieldKey === "autonomy_level" && val === DEFAULT_AUTONOMY && !delta[fieldKey]) return "inferred";
    return "explicit";
  }

  function budgetBadge(): BadgeKind {
    if (!flat?.budget) return "none";
    return "explicit";
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Panel header */}
      <div
        className="flex shrink-0 items-center justify-between px-5 py-3"
        style={{ borderBottom: "1px solid #1e2235" }}
      >
        <span className="font-mono text-xs tracking-[0.2em] text-muted">
          LIVE MANDATE
        </span>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-accent-green" />
          <span className="font-mono text-sm font-semibold text-accent-blue">
            {pct}%
          </span>
          {profileLoaded && (
            <span className="rounded border border-accent-green px-2 py-0.5 font-mono text-[10px] tracking-widest text-accent-green">
              profile loaded
            </span>
          )}
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-5 pb-6">
        {/* Completeness */}
        <div className="mb-4 mt-4">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="font-mono text-xs text-muted">completeness</span>
            <span className="font-mono text-sm font-semibold text-accent-blue">
              {pct}%
            </span>
          </div>
          {/* Progress bar with threshold tick */}
          <div
            className="relative h-1.5 w-full overflow-hidden rounded-full"
            style={{ background: "#1e2235" }}
          >
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-accent-blue transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
            {/* 70% threshold tick */}
            <div
              className="absolute inset-y-0 w-px bg-muted opacity-60"
              style={{ left: "70%" }}
            />
          </div>
          <p className="mt-1.5 font-mono text-[10px] text-muted">
            threshold: 70%{" "}
            {ready && (
              <span className="text-accent-green">— ready to match ✓</span>
            )}
          </p>
        </div>

        {/* Divider */}
        <div className="mb-4" style={{ borderTop: "1px solid #1e2235" }} />

        {/* CLASSIFICATION */}
        <SectionHeader label="CLASSIFICATION" />
        <FieldRow label="intent" value={flat?.intent_type} badge={badge("intent_type")} />
        <FieldRow label="vertical" value={flat?.vertical} badge={badge("vertical")} />
        <FieldRow label="category" value={flat?.category} badge={badge("category")} />

        <div className="my-3" style={{ borderTop: "1px solid #1e2235" }} />

        {/* TERMS */}
        <SectionHeader label="TERMS" />
        <FieldRow
          label="price ceiling"
          value={formatBudget(flat?.budget)}
          badge={budgetBadge()}
        />
        <FieldRow label="location" value={flat?.location} badge={badge("location")} />

        <div className="my-3" style={{ borderTop: "1px solid #1e2235" }} />

        {/* REQUIREMENTS */}
        <SectionHeader label="REQUIREMENTS" />
        <FieldRow label="condition" value={flat?.condition} badge={badge("condition")} />
        <FieldRow label="timing" value={flat?.timing} badge={badge("timing")} />
        <FieldRow
          label="preferences"
          value={flat?.style_preferences?.join(", ") || null}
          badge={badge("style_preferences")}
          mono
        />

        <div className="my-3" style={{ borderTop: "1px solid #1e2235" }} />

        {/* CONSTRAINTS */}
        <SectionHeader label="CONSTRAINTS" />
        <FieldRow
          label="dealbreakers"
          value={flat?.dealbreakers?.join(", ") || null}
          badge={badge("dealbreakers")}
          mono
        />
        <FieldRow
          label="autonomy"
          value={flat?.autonomy_level}
          badge={badge("autonomy_level")}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function MandateAgentPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [flatState, setFlatState] = useState<FlatMandateState | null>(null);
  const [completeness, setCompleteness] = useState(0);
  const [lastDelta, setLastDelta] = useState<Record<string, unknown>>({});
  const [profileLoaded, setProfileLoaded] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  const bootstrap = async () => {
    setStarting(true);
    setError(null);
    try {
      const session = await createMandateAgentSession();
      setConversationId(session.conversation.id);
      const flat = session.mandate.mandate_state ?? ormToFlat(session.mandate);
      setFlatState(flat);
      setCompleteness(session.mandate.completeness_score ?? 0);
      setLastDelta({});
      // Profile is considered loaded if location was pre-filled from persona
      const hasLocation = !!(flat.location);
      setProfileLoaded(hasLocation);
      setMessages([{ role: "agent", content: session.agent_message.content }]);
    } catch {
      setError("Unable to connect to the backend. Is the server running?");
    } finally {
      setStarting(false);
    }
  };

  useEffect(() => {
    void bootstrap();
  }, []);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const canSend = useMemo(
    () => Boolean(conversationId && input.trim().length > 0 && !loading && !starting),
    [conversationId, input, loading, starting],
  );

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!conversationId || !input.trim()) return;

    const message = input.trim();
    setInput("");
    setError(null);
    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", content: message }]);

    try {
      const response = await sendMandateAgentMessage(conversationId, message);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: response.agent_message.content },
      ]);
      setFlatState(response.mandate_state);
      setCompleteness(response.completeness_score);
      setLastDelta(response.mandate_delta as Record<string, unknown>);
    } catch {
      setError("Failed to send message.");
    } finally {
      setLoading(false);
    }
  };

  const onReset = () => {
    setConversationId(null);
    setMessages([]);
    setFlatState(null);
    setCompleteness(0);
    setLastDelta({});
    setProfileLoaded(false);
    void bootstrap();
  };

  return (
    <div
      className="flex"
      style={{ height: "calc(100vh - 56px)" }}
    >
      {/* ------------------------------------------------------------------ */}
      {/* LEFT — Chat panel                                                   */}
      {/* ------------------------------------------------------------------ */}
      <div
        className="flex w-[55%] shrink-0 flex-col"
        style={{ borderRight: "1px solid #1e2235" }}
      >
        {/* Chat header */}
        <div
          className="flex shrink-0 items-center gap-3 px-5 py-3"
          style={{ borderBottom: "1px solid #1e2235" }}
        >
          <span className="font-mono text-xs tracking-[0.15em] text-muted">
            MANDATE AGENT / MANDATE BUILD
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-accent-green" />
            <span className="font-mono text-xs text-muted">active</span>
          </span>
          <button
            onClick={onReset}
            disabled={starting}
            className="ml-auto rounded border border-border-dark px-3 py-1 font-mono text-xs text-muted transition-colors hover:border-muted hover:text-primary disabled:opacity-40"
          >
            reset
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mx-4 mt-3 rounded border border-red-900 bg-red-950 px-4 py-2 font-mono text-xs text-red-400">
            {error}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {starting && (
            <p className="font-mono text-xs text-muted">Connecting…</p>
          )}
          {messages.map((msg, i) => (
            <div key={i} className="mb-4">
              {msg.role === "user" ? (
                <div className="flex flex-col items-end">
                  <span className="mb-1 font-mono text-[10px] text-muted">
                    you
                  </span>
                  <div
                    className="max-w-[80%] rounded-lg px-4 py-2.5 text-sm leading-relaxed text-primary"
                    style={{ background: "#1a2440" }}
                  >
                    {msg.content}
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-start">
                  <span className="mb-1 font-mono text-[10px] text-muted">
                    agent
                  </span>
                  <div
                    className="max-w-[90%] rounded-lg px-4 py-3 text-sm leading-relaxed text-primary"
                    style={{ background: "#1c2030" }}
                  >
                    {renderMarkdown(msg.content)}
                  </div>
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="flex items-start">
              <div
                className="rounded-lg px-4 py-3 font-mono text-xs text-muted"
                style={{ background: "#1c2030" }}
              >
                thinking…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <form
          onSubmit={onSubmit}
          className="flex shrink-0 items-center gap-3 px-4 py-3"
          style={{ borderTop: "1px solid #1e2235" }}
        >
          <input
            className="flex-1 rounded-lg bg-card px-4 py-2.5 text-sm text-primary placeholder-muted outline-none ring-1 ring-border-dark transition-all focus:ring-accent-blue"
            placeholder="What are you looking for?"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!conversationId || starting}
          />
          <button
            type="submit"
            disabled={!canSend}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-blue text-base font-bold text-base transition-opacity disabled:opacity-30"
            style={{ color: "#0d0f14" }}
          >
            →
          </button>
        </form>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* RIGHT — Live Mandate panel                                          */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex min-w-0 flex-1 flex-col" style={{ background: "#111420" }}>
        <LiveMandatePanel
          flat={flatState}
          completeness={completeness}
          delta={lastDelta}
          profileLoaded={profileLoaded}
        />
      </div>
    </div>
  );
}
