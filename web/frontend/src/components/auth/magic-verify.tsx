"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, type ApiError } from "@/lib/api";

type Stage = "verifying" | "ok" | "error";

export function MagicVerify({ token }: { token: string }) {
  const router = useRouter();
  const [stage, setStage] = React.useState<Stage>("verifying");
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!token) {
      setStage("error");
      setError("Не передан токен. Откройте ссылку из письма.");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        await api.post("/api/auth/magic-link/verify", { token });
        if (cancelled) return;
        setStage("ok");
        setTimeout(() => router.replace("/cabinet"), 700);
      } catch (err) {
        if (cancelled) return;
        setStage("error");
        setError((err as ApiError).detail || "Ссылка недействительна или истекла.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, router]);

  if (stage === "verifying") {
    return (
      <div className="flex flex-col items-center gap-4 py-6">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Проверяем ссылку…</p>
      </div>
    );
  }

  if (stage === "ok") {
    return (
      <div className="flex flex-col items-center gap-4 py-6 text-center">
        <div className="grid h-12 w-12 place-items-center rounded-full bg-emerald-500/15 text-emerald-400">
          <CheckCircle2 className="h-6 w-6" />
        </div>
        <p className="text-sm text-muted-foreground">Готово, перенаправляем в кабинет…</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4 py-4 text-center">
      <div className="grid h-12 w-12 place-items-center rounded-full bg-destructive/15 text-destructive">
        <XCircle className="h-6 w-6" />
      </div>
      <div>
        <p className="text-base font-medium">Не удалось войти</p>
        <p className="text-sm text-muted-foreground">{error}</p>
      </div>
      <Button asChild variant="outline">
        <Link href="/auth/signin">Запросить новую ссылку</Link>
      </Button>
    </div>
  );
}
