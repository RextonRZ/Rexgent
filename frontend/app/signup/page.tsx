"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "@/components/auth/AuthShell";
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
            <Label htmlFor="name" className="text-xs text-muted-foreground">
              Name <span className="opacity-60">(optional)</span>
            </Label>
            <Input
              id="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Ada Director"
              className="mt-1 bg-background/50"
              autoFocus
            />
          </div>
          <div>
            <Label htmlFor="email" className="text-xs text-muted-foreground">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@studio.com"
              className="mt-1 bg-background/50"
            />
          </div>
          <div>
            <Label htmlFor="password" className="text-xs text-muted-foreground">
              Password
            </Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              className="mt-1 bg-background/50"
            />
            {passwordTooShort && (
              <p className="text-[11px] text-warn mt-1">
                Use at least 8 characters.
              </p>
            )}
          </div>
          <Button
            type="submit"
            className="w-full glow"
            size="lg"
            disabled={!canContinue}
          >
            Continue →
          </Button>
        </form>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-2">
            {PERSONAS.map((p) => (
              <button
                key={p.id}
                onClick={() => setPersona(p.id)}
                className={cn(
                  "text-left rounded-lg border p-3 transition-all",
                  persona === p.id
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-primary/40"
                )}
              >
                <div className="text-sm font-semibold">{p.label}</div>
                <div className="text-[11px] text-muted-foreground mt-0.5">
                  {p.desc}
                </div>
              </button>
            ))}
          </div>

          {errorMessage && <p className="text-sm text-bad">{errorMessage}</p>}

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setStep(1)}
              disabled={register.isPending}
            >
              Back
            </Button>
            <Button
              onClick={handleCreate}
              className="flex-1 glow"
              disabled={register.isPending}
            >
              {register.isPending ? "Creating…" : "Create account"}
            </Button>
          </div>
          <button
            onClick={handleCreate}
            disabled={register.isPending}
            className="w-full text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Skip for now
          </button>
        </div>
      )}
    </AuthShell>
  );
}
