"use client";

import { Suspense } from "react";
import AuthCallbackContent from "./content";

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
        </main>
      }
    >
      <AuthCallbackContent />
    </Suspense>
  );
}
