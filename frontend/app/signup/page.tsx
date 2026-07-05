"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BTN_PRIMARY, BTN_SECONDARY, CtaArrow } from "@/components/ui/cta";
import {
  AuthAlert,
  AuthShell,
  FIELD,
  FIELD_ERROR,
  LABEL,
  PasswordField,
} from "@/components/auth/AuthShell";
import { cn } from "@/lib/utils";
import { useAuth, useRegister } from "@/hooks/useAuth";

const PERSONAS = [
  { id: "creator", label: "Solo creator", desc: "I make films on my own." },
  { id: "studio", label: "Content studio", desc: "Small team, many projects." },
  { id: "brand", label: "Brand / marketing", desc: "Fast, on-brand video." },
  { id: "student", label: "Film student", desc: "Learning the craft." },
];

export default function SignupPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const register = useRegister();

  const [step, setStep] = useState<1 | 2>(1);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [persona, setPersona] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated) router.replace("/projects");
  }, [isAuthenticated, router]);

  const passwordTooShort = password.length > 0 && password.length < 8;
  const canContinue =
    email.trim().length > 3 && password.length >= 8 && !passwordTooShort;

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    if (canContinue) setStep(2);
  };

  const handleCreate = async () => {
    try {
      await register.mutateAsync({
        email: email.trim(),
        password,
        full_name: fullName.trim() || undefined,
        persona: persona || undefined,
      });
      router.replace("/projects");
    } catch {
      /* error surfaced below */
    }
  };

  const errorMessage =
    (register.error as { response?: { data?: { detail?: string } } } | null)
      ?.response?.data?.detail ||
    (register.isError ? "Unable to create account." : null);

  return (
    <AuthShell
      title={step === 1 ? "Create your studio" : "One quick thing"}
      subtitle={
        step === 1
          ? "Start directing in under a minute"
          : "What best describes you?"
      }
      footer={
        step === 1 ? (
          <>
            Already have an account?{" "}
            <Link href="/login" className="text-primary hover:underline">
              Sign in
            </Link>
          </>
        ) : undefined
      }
    >
      {step === 1 ? (
        <form onSubmit={handleNext} className="space-y-4">
          <div>
            <label htmlFor="name" className={LABEL}>
              Name <span className="text-zinc-500">(optional)</span>
            </label>
            <input
              id="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Ada Director"
              autoComplete="name"
              autoFocus
              className={FIELD}
            />
          </div>
          <div>
            <label htmlFor="email" className={LABEL}>
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@studio.com"
              className={FIELD}
            />
          </div>
          <div>
            <label htmlFor="password" className={LABEL}>
              Password
            </label>
            <PasswordField
              id="password"
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              placeholder="At least 8 characters"
              error={passwordTooShort}
            />
            {passwordTooShort && (
              <p className="mt-1.5 text-sm text-red-400">
                Use at least 8 characters.
              </p>
            )}
          </div>

          <Button
            type="submit"
            disabled={!canContinue}
            className={cn(
              "h-11 w-full",
              BTN_PRIMARY,
              "disabled:pointer-events-auto disabled:cursor-not-allowed"
            )}
          >
            Continue
            <CtaArrow />
          </Button>

          <p className="text-xs text-zinc-500">
            By continuing you agree to the{" "}
            <Link href="#" className="underline hover:text-zinc-300">
              Terms
            </Link>{" "}
            and{" "}
            <Link href="#" className="underline hover:text-zinc-300">
              Privacy Policy
            </Link>
            .
          </p>
        </form>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-2">
            {PERSONAS.map((p) => (
              <button
                key={p.id}
                onClick={() => setPersona(p.id)}
                className={cn(
                  "w-full rounded-lg border p-3 text-left outline-none transition-all",
                  "focus-visible:ring-2 focus-visible:ring-violet-500/40",
                  persona === p.id
                    ? "border-violet-500 bg-violet-500/10"
                    : "border-white/10 bg-zinc-900 hover:border-violet-500/40"
                )}
              >
                <div className="text-sm font-semibold">{p.label}</div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  {p.desc}
                </div>
              </button>
            ))}
          </div>

          <AuthAlert message={errorMessage} />

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setStep(1)}
              disabled={register.isPending}
              className={cn("h-11", BTN_SECONDARY)}
            >
              Back
            </Button>
            <Button
              onClick={handleCreate}
              disabled={register.isPending}
              className={cn(
                "h-11 flex-1",
                BTN_PRIMARY,
                "disabled:pointer-events-auto disabled:cursor-not-allowed"
              )}
            >
              {register.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Creating studio...
                </>
              ) : (
                <>
                  Create account
                  <CtaArrow />
                </>
              )}
            </Button>
          </div>
          <button
            onClick={handleCreate}
            disabled={register.isPending}
            className="w-full text-center text-xs text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-violet-500/40 rounded"
          >
            Skip for now
          </button>
        </div>
      )}
    </AuthShell>
  );
}
