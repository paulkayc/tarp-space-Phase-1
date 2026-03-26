"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    apiClient
      .get("/api/v1/onboarding/persona")
      .then((res) => {
        const { onboarding_completed_at } = res.data;
        if (!onboarding_completed_at) {
          router.replace("/onboarding");
        }
        // If completed, stay on home (future: redirect to /search or dashboard)
      })
      .catch(() => {
        // Unauthenticated or network error — send to onboarding so user can start
        router.replace("/onboarding");
      });
  }, [router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold">Tarp-Space</h1>
      <p className="mt-4 text-lg text-gray-600">Loading your profile…</p>
    </main>
  );
}
