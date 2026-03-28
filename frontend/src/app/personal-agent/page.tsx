"use client";

import {
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  createPersonalAgentSession,
  Persona,
  sendPersonalAgentMessage,
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
// Markdown renderer
// ---------------------------------------------------------------------------

function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split("\n");
  return lines.map((line, li) => {
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
      <span className="w-32 shrink-0 font-mono text-xs text-muted">{label}</span>
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
// Live Profile Panel
// ---------------------------------------------------------------------------

const PERSONA_THRESHOLD = 0.7;

function LiveProfilePanel({
  persona,
  completeness,
  delta,
}: {
  persona: Persona;
  completeness: number;
  delta: Persona;
}) {
  const pct = Math.round(completeness * 100);
  const ready = completeness >= PERSONA_THRESHOLD;

  function badge(key: keyof Persona): BadgeKind {
    const val = persona[key];
    const empty =
      val === undefined ||
      val === null ||
      val === "" ||
      (Array.isArray(val) && val.length === 0);
    if (empty) return "none";
    return "explicit";
  }

  const interestsStr =
    Array.isArray(persona.general_interests) && persona.general_interests.length > 0
      ? (persona.general_interests as string[]).join(", ")
      : null;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Panel header */}
      <div
        className="flex shrink-0 items-center justify-between px-5 py-3"
        style={{ borderBottom: "1px solid #1e2235" }}
      >
        <span className="font-mono text-xs tracking-[0.2em] text-muted">
          LIVE PROFILE
        </span>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-accent-green" />
          <span className="font-mono text-sm font-semibold text-accent-blue">
            {pct}%
          </span>
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
          <div
            className="relative h-1.5 w-full overflow-hidden rounded-full"
            style={{ background: "#1e2235" }}
          >
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-accent-blue transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
            <div
              className="absolute inset-y-0 w-px bg-muted opacity-60"
              style={{ left: "70%" }}
            />
          </div>
          <p className="mt-1.5 font-mono text-[10px] text-muted">
            threshold: 70%{" "}
            {ready && (
              <span className="text-accent-green">— profile ready ✓</span>
            )}
          </p>
        </div>

        <div className="mb-4" style={{ borderTop: "1px solid #1e2235" }} />

        {/* IDENTITY */}
        <SectionHeader label="IDENTITY" />
        <FieldRow
          label="name"
          value={persona.name as string | undefined}
          badge={badge("name")}
        />
        <FieldRow
          label="home city"
          value={persona.home_city as string | undefined}
          badge={badge("home_city")}
        />

        <div className="my-3" style={{ borderTop: "1px solid #1e2235" }} />

        {/* PREFERENCES */}
        <SectionHeader label="PREFERENCES" />
        <FieldRow
          label="comm style"
          value={persona.communication_style as string | undefined}
          badge={badge("communication_style")}
        />
        <FieldRow
          label="deal focus"
          value={persona.deal_sensitivity as string | undefined}
          badge={badge("deal_sensitivity")}
        />

        <div className="my-3" style={{ borderTop: "1px solid #1e2235" }} />

        {/* INTERESTS */}
        <SectionHeader label="INTERESTS" />
        <FieldRow
          label="categories"
          value={interestsStr}
          badge={badge("general_interests")}
          mono
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function PersonalAgentPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [persona, setPersona] = useState<Persona>({});
  const [completeness, setCompleteness] = useState(0);
  const [lastDelta, setLastDelta] = useState<Persona>({});

  const bottomRef = useRef<HTMLDivElement>(null);

  const bootstrap = async () => {
    setStarting(true);
    setError(null);
    try {
      const session = await createPersonalAgentSession();
      setConversationId(session.conversation.id);
      setPersona(session.persona ?? {});
      setCompleteness(0);
      setLastDelta({});
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
      const response = await sendPersonalAgentMessage(conversationId, message);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: response.agent_message.content },
      ]);
      setPersona(response.persona);
      setCompleteness(response.completeness_score);
      setLastDelta(response.persona_delta);
    } catch {
      setError("Failed to send message.");
    } finally {
      setLoading(false);
    }
  };

  const onReset = () => {
    setConversationId(null);
    setMessages([]);
    setPersona({});
    setCompleteness(0);
    setLastDelta({});
    void bootstrap();
  };

  return (
    <div className="flex" style={{ height: "calc(100vh - 56px)" }}>
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
            PERSONAL AGENT / PROFILE BUILD
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
            placeholder="Tell me about yourself…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!conversationId || starting}
          />
          <button
            type="submit"
            disabled={!canSend}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-blue text-base font-bold transition-opacity disabled:opacity-30"
            style={{ color: "#0d0f14" }}
          >
            →
          </button>
        </form>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* RIGHT — Live Profile panel                                          */}
      {/* ------------------------------------------------------------------ */}
      <div
        className="flex min-w-0 flex-1 flex-col"
        style={{ background: "#111420" }}
      >
        <LiveProfilePanel
          persona={persona}
          completeness={completeness}
          delta={lastDelta}
        />
      </div>
    </div>
  );
}
