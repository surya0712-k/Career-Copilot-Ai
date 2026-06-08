"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

// Share one in-flight exchange per OAuth code (React Strict Mode mounts twice).
const exchangePromises = new Map<
  string,
  Promise<{ access_token: string; user: unknown }>
>();

function exchangeGitHubCode(code: string) {
  let promise = exchangePromises.get(code);
  if (!promise) {
    promise = api.githubAuth(code);
    exchangePromises.set(code, promise);
    promise.finally(() => exchangePromises.delete(code));
  }
  return promise;
}

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

    let active = true;

    exchangeGitHubCode(code)
      .then((data) => {
        if (!active) return;
        localStorage.setItem("token", data.access_token);
        router.replace("/dashboard");
      })
      .catch((e) => {
        if (!active) return;
        setError(e instanceof Error ? e.message : "Sign-in failed");
      });

    return () => {
      active = false;
    };
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
