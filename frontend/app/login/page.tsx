"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BTN_PRIMARY, CtaArrow } from "@/components/ui/cta";
import {
  AuthAlert,
  AuthShell,
  FIELD,
  LABEL,
  PasswordField,
} from "@/components/auth/AuthShell";
import { cn } from "@/lib/utils";
import { useAuth, useLogin } from "@/hooks/useAuth";

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (isAuthenticated) router.replace("/projects");
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login.mutateAsync({ email, password });
      router.replace("/projects");
    } catch {
      /* error surfaced below */
    }
  };

  const errorMessage =
    (login.error as { response?: { data?: { detail?: string } } } | null)
      ?.response?.data?.detail || (login.isError ? "Unable to sign in." : null);

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your studio"
      footer={
        <>
          New to Rexgent?{" "}
          <Link href="/signup" className="text-primary hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className={LABEL}>
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            autoFocus
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@studio.com"
            className={FIELD}
          />
        </div>
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label htmlFor="password" className={cn(LABEL, "mb-0")}>
              Password
            </label>
            <Link
              href="#"
              className="text-xs text-zinc-500 transition-colors hover:text-zinc-300"
            >
              Forgot password?
            </Link>
          </div>
          <PasswordField
            id="password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
            placeholder="••••••••"
          />
        </div>

        <AuthAlert message={errorMessage} />

        <Button
          type="submit"
          disabled={login.isPending}
          className={cn(
            "h-11 w-full",
            BTN_PRIMARY,
            "disabled:pointer-events-auto disabled:cursor-not-allowed"
          )}
        >
          {login.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Signing in...
            </>
          ) : (
            <>
              Sign in
              <CtaArrow />
            </>
          )}
        </Button>
      </form>
    </AuthShell>
  );
}
