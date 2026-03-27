export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold">Tarp-Space</h1>
      <p className="mt-4 text-lg text-gray-600">
        Local marketplace powered by AI agents — Phase 1 scaffold
      </p>
      <a
        href="/personal-agent"
        className="mt-6 rounded bg-black px-4 py-2 text-white"
      >
        Open Personal Agent
      </a>
    </main>
  );
}
