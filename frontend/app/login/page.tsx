"use client";

import { getGitHubAuthUrl, isGitHubAuthConfigured } from "@/lib/api";
import { Brain } from "lucide-react";

export default function LoginPage() {
  const configured = isGitHubAuthConfigured();

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="card w-full max-w-md text-center">
        <Brain className="mx-auto mb-4 h-12 w-12 text-brand-500" />
        <h1 className="mb-2 text-2xl font-bold">Welcome Back</h1>
        <p className="mb-8 text-white/60">
          Sign in with GitHub to connect your profile and start your career journey.
        </p>
        {configured ? (
          <a href={getGitHubAuthUrl()} className="btn-primary block w-full py-3">
            Sign in with GitHub
          </a>
        ) : (
          <p className="text-sm text-red-400">
            GitHub OAuth is not configured. Set NEXT_PUBLIC_GITHUB_CLIENT_ID in frontend/.env.local
            and restart the dev server.
          </p>
        )}
      </div>
    </main>
  );
}
