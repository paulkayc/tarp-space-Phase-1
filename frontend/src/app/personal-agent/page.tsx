"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  createPersonalAgentSession,
  listPersonalMemories,
  sendPersonalAgentMessage,
} from "@/lib/api";

type ChatMessage = {
  role: "user" | "agent";
  content: string;
};

export default function PersonalAgentPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [memories, setMemories] = useState<Array<{ id: string; content: string }>>(
    [],
  );

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const session = await createPersonalAgentSession();
        setConversationId(session.conversation.id);
        setMessages([{ role: "agent", content: session.agent_message.content }]);
      } catch {
        setError("Unable to create personal agent session.");
      }
    };
    void bootstrap();
  }, []);

  const canSend = useMemo(
    () => Boolean(conversationId && input.trim().length > 0 && !loading),
    [conversationId, input, loading],
  );

  const refreshMemories = async () => {
    try {
      const data = await listPersonalMemories();
      setMemories(data.memories ?? []);
    } catch {
      // best effort in phase 4
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
      const response = await sendPersonalAgentMessage(conversationId, message);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: response.agent_message.content },
      ]);
      await refreshMemories();
    } catch {
      setError("Failed to send message to Personal Agent.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 p-6">
      <header>
        <h1 className="text-3xl font-bold">Personal Agent</h1>
        <p className="text-gray-600">
          Ask onboarding questions, save preferences, and inspect memory snippets.
        </p>
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
              placeholder="Tell the agent what you prefer..."
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
          <h2 className="mb-3 font-semibold">Memory Panel</h2>
          <button
            onClick={() => void refreshMemories()}
            className="mb-3 rounded border px-3 py-1 text-sm"
          >
            Refresh
          </button>
          <div className="space-y-2">
            {memories.length === 0 ? (
              <p className="text-sm text-gray-500">No memories yet.</p>
            ) : (
              memories.map((memory) => (
                <div key={memory.id} className="rounded bg-gray-50 p-2 text-sm">
                  {memory.content}
                </div>
              ))
            )}
          </div>
        </aside>
      </section>
    </main>
  );
}
