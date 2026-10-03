"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Lock, Mail } from "lucide-react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import PasswordInput from "@/components/ui/PasswordInput";
import { authErrorKey } from "@/lib/auth/cognito";
import { useSession } from "@/lib/auth/SessionProvider";
import { isLocale } from "@/lib/i18n/config";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** Only paths on this site are accepted as a return address, so a crafted link cannot redirect elsewhere. */
export function safeNext(value: string | null, fallback: string): string {
  return value && value.startsWith("/") && !value.startsWith("//") && isLocale(value.split("/")[1]) ? value : fallback;
}

export default function LoginForm() {
  const { signIn } = useSession();
  const { t, href } = useI18n();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"), href("/dashboard/"));
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
      setError(t.login.errors[authErrorKey(err)]);
      setLoading(false);
    }
  }

  return (
    <>
      <div className="mb-7">
        <h1 className="text-2xl font-bold tracking-tight text-text-dark">{t.login.title}</h1>
        <p className="mt-2 max-w-xs text-[15px] leading-relaxed text-text-gray">{t.login.subtitle}</p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Input label={t.login.email} name="email" type="email" inputMode="email" autoComplete="username" spellCheck={false} required value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder={t.login.emailPlaceholder} leadingIcon={<Mail className="h-[18px] w-[18px]" aria-hidden="true" />} />
        <PasswordInput label={t.login.password} name="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)}
          leadingIcon={<Lock className="h-[18px] w-[18px]" aria-hidden="true" />} />
        {error && <div role="alert" className="rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
        <Button type="submit" loading={loading} disabled={!email || !password} className="w-full">{t.login.submit}</Button>
      </form>
      <p className="mt-6 text-xs leading-relaxed text-text-light">{t.login.internalNote}</p>
    </>
  );
}
