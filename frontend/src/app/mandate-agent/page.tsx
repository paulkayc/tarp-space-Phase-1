"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  createMandateAgentSession,
  getMandateAgentMandate,
  MandateState,
  sendMandateAgentMessage,
} from "@/lib/api";

type ChatMessage = {
  role: "user" | "agent";
  content: string;
};

function MandatePanel({ mandate }: { mandate: MandateState | null }) {
  if (!mandate) {
    return <p className="text-sm text-gray-500">No mandate yet.</p>;
  }

  const score = Math.round((mandate.completeness_score ?? 0) * 100);
  const state = mandate.mandate_state ?? {};

  const rows: Array<{ label: string; value: string | null }> = [
    { label: "Intent", value: mandate.intent_type },
    { label: "Vertical", value: mandate.vertical },
    { label: "Category", value: mandate.category },
    {
      label: "Budget",
      value: (() => {
        const price = mandate.negotiation_range?.find(
          (r) => r.dimension === "price",
        );
        if (!price) return null;
        if (price.min != null && price.max != null)
          return `$${price.min}–$${price.max}`;
        if (price.max != null) return `up to $${price.max}`;
        if (price.min != null) return `at least $${price.min}`;
        return null;
      })(),
    },
    {
      label: "Location",
      value:
        mandate.hard_constraints?.find((c) => c.field === "location")?.value ??
        null,
    },
    {
      label: "Condition",
      value:
        mandate.hard_constraints?.find((c) => c.field === "condition")?.value ??
        null,
    },
    {
      label: "Timing",
      value:
        mandate.hard_constraints?.find((c) => c.field === "timing")?.value ??
        null,
    },
    {
      label: "Style",
      value:
        mandate.soft_preferences
          ?.filter((p) => p.field === "style")
          .map((p) => p.value)
          .join(", ") || null,
    },
    {
      label: "Dealbreakers",
      value: mandate.dealbreakers?.join(", ") || null,
    },
    { label: "Autonomy", value: mandate.autonomy_level },
  ];

  const gaps = Object.keys(state).length;

  return (
    <div className="space-y-3">
      <div>
        <div className="mb-1 flex items-center justify-between text-sm">
          <span className="font-medium">Completeness</span>
          <span className="font-semibold">{score}%</span>
        </div>
        <div className="h-2 w-full rounded-full bg-gray-200">
          <div
            className="h-2 rounded-full bg-black transition-all"
            style={{ width: `${score}%` }}
          />
        </div>
      </div>

      <div className="divide-y rounded border text-sm">
        {rows.map(({ label, value }) => (
          <div key={label} className="flex items-start gap-2 px-3 py-2">
            <span className="w-24 shrink-0 text-gray-500">{label}</span>
            <span className={value ? "text-gray-900" : "text-gray-300"}>
              {value ?? "—"}
            </span>
          </div>
        ))}
      </div>

      {mandate.is_active && (
        <p className="rounded bg-green-50 px-3 py-2 text-sm text-green-700">
          ✓ Mandate complete
        </p>
      )}
    </div>
  );
}

export default function MandateAgentPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mandate, setMandate] = useState<MandateState | null>(null);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const session = await createMandateAgentSession();
        setConversationId(session.conversation.id);
        setMandate(session.mandate);
        setMessages([{ role: "agent", content: session.agent_message.content }]);
      } catch {
        setError("Unable to create mandate agent session.");
      }
    };
    void bootstrap();
  }, []);

  const canSend = useMemo(
    () => Boolean(conversationId && input.trim().length > 0 && !loading),
    [conversationId, input, loading],
  );

  const refreshMandate = async () => {
    if (!conversationId) return;
    try {
      const data = await getMandateAgentMandate(conversationId);
      setMandate(data);
    } catch {
      // best effort
    }
  };

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
      await refreshMandate();
    } catch {
      setError("Failed to send message to Mandate Agent.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 p-6">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">Mandate Agent</h1>
          <p className="text-gray-600">
            Tells the agent what you want — intent, category, budget, location,
            and conditions. Builds a structured mandate for marketplace matching.
          </p>
        </div>
        <a href="/" className="rounded border px-3 py-1 text-sm text-gray-600 hover:bg-gray-50">
          ← Home
        </a>
      </header>

      {error ? (
        <p className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      <section className="grid gap-6 md:grid-cols-[2fr_1fr]">
        <div className="rounded border p-4">
          <h2 className="mb-3 font-semibold">Chat</h2>
          <div className="mb-4 h-96 space-y-2 overflow-y-auto rounded border bg-gray-50 p-3">
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`rounded p-2 text-sm ${
                  message.role === "agent" ? "bg-white" : "bg-blue-50"
                }`}
              >
                <strong className="mr-1 uppercase">{message.role}:</strong>
                {message.content}
              </div>
            ))}
          </div>

          <form className="flex gap-2" onSubmit={onSubmit}>
            <input
              className="flex-1 rounded border px-3 py-2"
              placeholder="e.g. I want to buy a sofa in Houston under $600..."
              value={input}
              onChange={(event) => setInput(event.target.value)}
            />
            <button
              type="submit"
              disabled={!canSend}
              className="rounded bg-black px-4 py-2 text-white disabled:opacity-40"
            >
              {loading ? "Sending..." : "Send"}
            </button>
          </form>
        </div>

        <aside className="rounded border p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Mandate State</h2>
            <button
              onClick={() => void refreshMandate()}
              className="rounded border px-3 py-1 text-sm"
            >
              Refresh
            </button>
          </div>
          <MandatePanel mandate={mandate} />
        </aside>
      </section>
    </main>
  );
}
