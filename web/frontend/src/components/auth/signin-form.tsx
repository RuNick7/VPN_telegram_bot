"use client";

import * as React from "react";
import { ArrowRight, Loader2, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type ApiError } from "@/lib/api";

export function SignInForm() {
  const [email, setEmail] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [sent, setSent] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/api/auth/email/request", { email: email.trim() });
      setSent(true);
    } catch (err) {
      setError((err as ApiError).detail || "Не удалось отправить ссылку");
    } finally {
      setSubmitting(false);
    }
  };

  if (sent) {
    return (
      <div className="flex flex-col items-center gap-4 py-4 text-center">
        <div className="grid h-12 w-12 place-items-center rounded-full bg-emerald-500/15 text-emerald-400">
          <Mail className="h-6 w-6" />
        </div>
        <div>
          <p className="text-base font-medium">Письмо отправлено</p>
          <p className="text-sm text-muted-foreground">
            Мы отправили вход на <span className="font-mono text-foreground">{email}</span>.
            Ссылка действительна 15 минут.
          </p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5">
      <div className="grid gap-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="you@kaira.app"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={submitting}
        />
        <p className="text-xs text-muted-foreground">
          Введите email, который вы привязали при регистрации. Мы пришлём
          одноразовую ссылку для входа.
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" size="lg" variant="gradient" disabled={submitting || !email.trim()}>
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
        Получить ссылку
      </Button>
    </form>
  );
}
