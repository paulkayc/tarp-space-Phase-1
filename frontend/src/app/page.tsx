export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold">Tarp-Space</h1>
      <p className="mt-4 text-lg text-gray-600">
        Local marketplace powered by AI agents — Phase 1 scaffold
      </p>

      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        <a
          href="/personal-agent"
          className="flex flex-col rounded border p-6 text-left hover:bg-gray-50"
        >
          <span className="mb-1 text-lg font-semibold">Personal Agent</span>
          <span className="text-sm text-gray-500">
            Learns who you are — name, city, preferences, and communication
            style. Saves everything to long-term memory.
          </span>
          <span className="mt-4 self-start rounded bg-black px-4 py-2 text-sm text-white">
            Open →
          </span>
        </a>

        <a
          href="/mandate-agent"
          className="flex flex-col rounded border p-6 text-left hover:bg-gray-50"
        >
          <span className="mb-1 text-lg font-semibold">Mandate Agent</span>
          <span className="text-sm text-gray-500">
            Learns what you want right now — intent, category, budget,
            location, and conditions. Builds a structured mandate.
          </span>
          <span className="mt-4 self-start rounded bg-black px-4 py-2 text-sm text-white">
            Open →
          </span>
        </a>
      </div>
    </main>
  );
}
