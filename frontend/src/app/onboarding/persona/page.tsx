"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";

interface PersonaData {
  persona: Record<string, unknown>;
  completeness_score: number;
  onboarding_completed_at: string | null;
}

type SourceBadge = "explicit" | "persona" | "declined" | "inferred";

interface FieldRow {
  label: string;
  dotPath: string;
  value: unknown;
  source: SourceBadge;
  editable: boolean;
}

function getBadgeStyle(source: SourceBadge) {
  switch (source) {
    case "explicit":
      return "bg-green-100 text-green-700";
    case "persona":
      return "bg-blue-100 text-blue-700";
    case "declined":
      return "bg-gray-100 text-gray-500";
    case "inferred":
      return "bg-yellow-100 text-yellow-700";
  }
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function extractRows(persona: Record<string, unknown>): Record<string, FieldRow[]> {
  const meta = (persona["_meta"] as Record<string, unknown>) ?? {};
  const declined = new Set<string>((meta["declined"] as string[]) ?? []);
  const sourceFlagsRaw = (meta["source_flags"] as Record<string, string>) ?? {};

  function sourceFor(dotPath: string): SourceBadge {
    if (declined.has(dotPath)) return "declined";
    const top = dotPath.split(".")[0];
    const flag = sourceFlagsRaw[dotPath] ?? sourceFlagsRaw[top];
    if (flag === "explicit") return "explicit";
    if (flag === "persona") return "persona";
    if (flag === "inferred") return "inferred";
    return "persona"; // default
  }

  function makeRow(
    label: string,
    dotPath: string,
    value: unknown,
    editable = true
  ): FieldRow {
    return { label, dotPath, value, source: sourceFor(dotPath), editable };
  }

  const identity = (persona["identity"] as Record<string, unknown>) ?? {};
  const location = (persona["location"] as Record<string, unknown>) ?? {};
  const preferences = (persona["preferences"] as Record<string, unknown>) ?? {};
  const lifestyle = (persona["lifestyle"] as Record<string, unknown>) ?? {};
  const trustSeeds = (persona["trust_seeds"] as Record<string, unknown>) ?? {};

  return {
    Identity: [
      makeRow("Name", "identity.display_name", identity["display_name"]),
      makeRow("Gender", "identity.sex", identity["sex"]),
      makeRow("Phone", "identity.phone", identity["phone"]),
    ].filter((r) => r.value !== undefined || r.source === "declined"),

    Location: [
      makeRow("Neighborhood", "location.neighborhood", location["neighborhood"]),
      makeRow("City", "location.city", location["city"]),
      makeRow("State", "location.state", location["state"]),
    ].filter((r) => r.value !== undefined || r.source === "declined"),

    Preferences: [
      makeRow(
        "Style affinities",
        "preferences.style_affinities",
        preferences["style_affinities"]
      ),
      makeRow(
        "Style dealbreakers",
        "preferences.style_dealbreakers",
        preferences["style_dealbreakers"]
      ),
      makeRow(
        "Goods budget",
        "preferences.typical_budget_goods",
        preferences["typical_budget_goods"]
      ),
      makeRow(
        "Services budget",
        "preferences.typical_budget_services",
        preferences["typical_budget_services"]
      ),
    ].filter((r) => r.value !== undefined || r.source === "declined"),

    Lifestyle: [
      makeRow("Has pets", "lifestyle.has_pets", lifestyle["has_pets"]),
      makeRow("Home type", "lifestyle.home_type", lifestyle["home_type"]),
    ].filter((r) => r.value !== undefined || r.source === "declined"),

    Communities: [
      makeRow(
        "Communities",
        "trust_seeds.community_names",
        trustSeeds["community_names"]
      ),
    ].filter((r) => r.value !== undefined || r.source === "declined"),
  };
}

function FieldEditor({
  row,
  onSave,
}: {
  row: FieldRow;
  onSave: (path: string, value: unknown) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(displayValue(row.value));
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await onSave(row.dotPath, draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  if (!row.editable || row.source === "declined") {
    return (
      <span className="text-gray-700 text-sm">{displayValue(row.value)}</span>
    );
  }

  if (editing) {
    return (
      <div className="flex items-center gap-2">
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="border border-gray-300 rounded px-2 py-0.5 text-sm focus:outline-none focus:border-blue-400"
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") setEditing(false);
          }}
        />
        <button
          onClick={save}
          disabled={saving}
          className="text-xs text-blue-600 hover:underline disabled:opacity-50"
        >
          Save
        </button>
        <button
          onClick={() => setEditing(false)}
          className="text-xs text-gray-400 hover:underline"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={() => setEditing(true)}
      className="text-sm text-gray-700 hover:text-blue-600 group flex items-center gap-1"
    >
      <span>{displayValue(row.value)}</span>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="w-3.5 h-3.5 opacity-0 group-hover:opacity-50 transition-opacity"
      >
        <path d="M5.433 13.917l1.262-3.155A4 4 0 017.58 9.42l6.92-6.918a2.121 2.121 0 013 3l-6.92 6.918c-.383.383-.84.685-1.343.886l-3.154 1.262a.5.5 0 01-.65-.65z" />
        <path d="M3.5 5.75c0-.69.56-1.25 1.25-1.25H10A.75.75 0 0010 3H4.75A2.75 2.75 0 002 5.75v9.5A2.75 2.75 0 004.75 18h9.5A2.75 2.75 0 0017 15.25V10a.75.75 0 00-1.5 0v5.25c0 .69-.56 1.25-1.25 1.25h-9.5c-.69 0-1.25-.56-1.25-1.25v-9.5z" />
      </svg>
    </button>
  );
}

export default function PersonaPage() {
  const router = useRouter();
  const [data, setData] = useState<PersonaData | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    const res = await apiClient.get<PersonaData>("/api/v1/onboarding/persona");
    setData(res.data);
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSave(path: string, rawValue: string) {
    // Attempt to parse JSON (handles booleans, numbers, arrays); fall back to string
    let value: unknown = rawValue;
    try {
      value = JSON.parse(rawValue);
    } catch {
      value = rawValue;
    }
    await apiClient.patch("/api/v1/onboarding/persona/fields", { path, value });
    await load();
  }

  if (loading || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-400 text-sm">Loading your profile…</p>
      </div>
    );
  }

  const sections = extractRows(data.persona);
  const pct = Math.round(data.completeness_score * 100);
  const isComplete = data.completeness_score >= 0.7;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
        <span className="text-xl font-semibold tracking-tight">Tarp-Space</span>
        <Link
          href="/onboarding"
          className="text-sm text-blue-600 hover:underline"
        >
          ← Back to chat
        </Link>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Your Profile</h1>
          <span className="text-sm text-gray-500">{pct}% complete</span>
        </div>

        {/* Completeness bar */}
        <div className="mb-8">
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          {!isComplete && (
            <p className="mt-2 text-sm text-gray-500">
              Continue the conversation to reach 70% and unlock search.{" "}
              <Link
                href="/onboarding"
                className="text-blue-600 hover:underline"
              >
                Continue onboarding →
              </Link>
            </p>
          )}
        </div>

        {/* Sections */}
        <div className="space-y-6">
          {Object.entries(sections).map(([section, rows]) =>
            rows.length === 0 ? null : (
              <div key={section} className="bg-white rounded-xl border border-gray-100 overflow-hidden">
                <div className="px-5 py-3 border-b border-gray-50 bg-gray-50">
                  <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">
                    {section}
                  </h2>
                </div>
                <div className="divide-y divide-gray-50">
                  {rows.map((row) => (
                    <div
                      key={row.dotPath}
                      className="flex items-center justify-between px-5 py-3 gap-4"
                    >
                      <span className="text-sm text-gray-500 w-36 shrink-0">
                        {row.label}
                      </span>
                      <div className="flex-1">
                        <FieldEditor row={row} onSave={handleSave} />
                      </div>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${getBadgeStyle(row.source)}`}
                      >
                        {row.source}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )
          )}
        </div>

        {/* Legend */}
        <div className="mt-8 flex flex-wrap gap-3 text-xs text-gray-500">
          <span>Source badges:</span>
          {(["explicit", "persona", "inferred", "declined"] as SourceBadge[]).map(
            (s) => (
              <span
                key={s}
                className={`px-2 py-0.5 rounded-full font-medium ${getBadgeStyle(s)}`}
              >
                {s}
              </span>
            )
          )}
        </div>
      </main>
    </div>
  );
}
