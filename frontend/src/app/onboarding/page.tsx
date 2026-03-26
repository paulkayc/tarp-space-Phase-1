"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient, ssePost } from "@/lib/api";

interface Message {
  role: "agent" | "user";
  content: string;
}

export default function OnboardingPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "agent",
      content:
        "Hi! I'm here to help set up your Tarp-Space profile. Tell me a little about yourself — your name, where you live, what you're into.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [completeness, setCompleteness] = useState(0);
  const [done, setDone] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Load current completeness on mount
  useEffect(() => {
    apiClient.get("/api/v1/onboarding/persona").then((res) => {
      const score: number = res.data.completeness_score ?? 0;
      setCompleteness(score);
      if (res.data.onboarding_completed_at) {
        setDone(true);
      }
    });
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);

    setMessages((prev) => [...prev, { role: "user", content: text }]);

    // Placeholder for streaming agent reply
    setMessages((prev) => [...prev, { role: "agent", content: "" }]);

    try {
      const response = await ssePost("/api/v1/onboarding/message", {
        content: text,
      });

      if (!response.body) throw new Error("no body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let agentText = "";

      while (true) {
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const json = line.slice(6).trim();
          if (!json) continue;
          try {
            const event = JSON.parse(json);
            if (event.type === "token") {
              agentText += event.content;
              setMessages((prev) => {
                const copy = [...prev];
                copy[copy.length - 1] = { role: "agent", content: agentText };
                return copy;
              });
            } else if (event.type === "done") {
              setCompleteness(event.completeness_score ?? 0);
              if (event.onboarding_complete) {
                setDone(true);
              }
            }
          } catch {
            // malformed SSE line — skip
          }
        }
      }
    } catch {
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "agent",
          content: "Sorry, something went wrong. Please try again.",
        };
        return copy;
      });
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const pct = Math.round(completeness * 100);

  return (
    <div className="flex flex-col min-h-screen bg-white">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <span className="text-xl font-semibold tracking-tight">Tarp-Space</span>
        <button
          onClick={async () => {
            await apiClient.post("/api/v1/onboarding/skip");
            router.replace("/");
          }}
          className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
        >
          Skip for now
        </button>
      </header>

      {/* Completeness bar */}
      <div className="px-6 pt-3 pb-1">
        <div className="flex items-center gap-3">
          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-xs text-gray-400 w-10 text-right">{pct}%</span>
        </div>
      </div>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto px-4 py-6 max-w-2xl mx-auto w-full">
        <div className="flex flex-col gap-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-blue-500 text-white rounded-br-sm"
                    : "bg-gray-100 text-gray-800 rounded-bl-sm"
                }`}
              >
                {msg.content || (
                  <span className="inline-block w-8 animate-pulse text-gray-400">
                    …
                  </span>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </main>

      {/* Completion CTA */}
      {done && (
        <div className="flex justify-center pb-4">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 bg-blue-500 text-white text-sm font-medium px-5 py-2.5 rounded-full hover:bg-blue-600 transition-colors"
          >
            Start your first search →
          </Link>
        </div>
      )}

      {/* Input */}
      {!done && (
        <footer className="px-4 pb-6 max-w-2xl mx-auto w-full">
          <div className="flex items-end gap-2 border border-gray-200 rounded-2xl px-4 py-2 focus-within:border-blue-400 transition-colors">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Tell me about yourself…"
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm outline-none placeholder-gray-400 py-1 max-h-32"
              style={{ minHeight: "24px" }}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || sending}
              className="mb-0.5 p-1.5 rounded-lg bg-blue-500 text-white disabled:opacity-40 hover:bg-blue-600 transition-colors"
              aria-label="Send"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                className="w-4 h-4"
              >
                <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
              </svg>
            </button>
          </div>
          <p className="mt-2 text-center text-xs text-gray-400">
            Press Enter to send · Shift+Enter for new line ·{" "}
            <Link
              href="/onboarding/persona"
              className="underline hover:text-gray-600"
            >
              Review your profile
            </Link>
          </p>
        </footer>
      )}
    </div>
  );
}
