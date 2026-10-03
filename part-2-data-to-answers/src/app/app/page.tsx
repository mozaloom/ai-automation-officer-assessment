"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/auth/SessionProvider";

export default function Home() {
  const { session, ready } = useSession();
  const router = useRouter();
  useEffect(() => { if (ready) router.replace(session ? "/dashboard/" : "/login/"); }, [ready, session, router]);
  return <div className="flex min-h-screen items-center justify-center" role="status" aria-label="Loading"><div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-blue/20 border-t-brand-blue" /></div>;
}
