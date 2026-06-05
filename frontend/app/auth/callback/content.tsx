"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

export default function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code) {
      setError("No authorization code received");
      return;
    }

    api
      .githubAuth(code)
      .then((data) => {
        localStorage.setItem("token", data.access_token);
        router.push("/onboarding");
      })
      .catch((e) => setError(e.message));
  }, [searchParams, router]);

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div className="card text-center">
          <p className="text-red-400">{error}</p>
          <a href="/login" className="btn-primary mt-4 inline-block">
            Try Again
          </a>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="card text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
        <p className="mt-4 text-white/60">Signing you in...</p>
      </div>
    </main>
  );
}
