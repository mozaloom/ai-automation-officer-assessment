"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Mail, Lock } from "lucide-react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import PasswordInput from "@/components/ui/PasswordInput";
import { friendlyAuthError } from "@/lib/auth/cognito";
import { useSession } from "@/lib/auth/SessionProvider";

// Same shape as Clarity's auth controls: 48px fields with 6px corners.
const FIELD = "h-12 !py-0 !rounded-md !shadow-none !border-[#d0d5dd] hover:!border-[#9aa3d6] focus:!border-brand-blue focus:!ring-4 focus:!ring-brand-blue/15";

function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/dashboard/";
}

export default function LoginForm() {
  const { signIn } = useSession();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signIn(email, password);
      router.replace(next);
    } catch (err) {
      setError(friendlyAuthError(err));
      setLoading(false);
    }
  }

  return (
    <>
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-bold tracking-[-0.02em] text-text-dark sm:text-[28px]">Welcome <span className="text-brand-blue">back</span></h1>
        <p className="mx-auto mt-3 max-w-xs text-[15px] leading-relaxed text-[#5b5870]">Sign in to see where your products are available.</p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Input label="Email" name="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" className={FIELD} leadingIcon={<Mail className="h-[18px] w-[18px]" aria-hidden="true" />} />
        <PasswordInput label="Password" name="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Your password" className={FIELD} leadingIcon={<Lock className="h-[18px] w-[18px]" aria-hidden="true" />} />
        {error && <div role="alert" className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
        <Button type="submit" variant="pill" loading={loading} disabled={!email || !password} className="h-12 w-full !rounded-md !py-0">Sign in</Button>
      </form>
      <p className="mt-6 text-center text-xs leading-relaxed text-[#8a869a]">Internal tool. Access is limited to invited users.</p>
    </>
  );
}
