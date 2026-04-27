"use client";

import * as React from "react";
import { CheckCircle2, Loader2, Ticket } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type ApiError } from "@/lib/api";

type Result =
  | { ok: true; type: "gift" | "days"; added_days: number; code: string }
  | { ok: false; message: string };

export function PromoForm() {
  const [code, setCode] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [result, setResult] = React.useState<Result | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setResult(null);
    try {
      const data = await api.post<{ ok: true; type: "gift" | "days"; added_days: number; code: string }>(
        "/api/promo/redeem",
        { code: code.trim() },
      );
      setResult(data);
      setCode("");
    } catch (err) {
      setResult({ ok: false, message: (err as ApiError).detail || "Не удалось активировать промокод" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div className="grid gap-2">
        <Label htmlFor="promo">Промокод</Label>
        <Input
          id="promo"
          autoCapitalize="characters"
          placeholder="KAIRA-XXXX-XXXX"
          required
          value={code}
          onChange={(event) => setCode(event.target.value.toUpperCase())}
          disabled={submitting}
          className="font-mono"
        />
        <p className="text-xs text-muted-foreground">
          Подарочные промокоды добавляют дни подписки сразу после активации.
        </p>
      </div>
      <Button type="submit" size="lg" variant="gradient" disabled={submitting || !code.trim()}>
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Ticket className="h-4 w-4" />}
        Активировать
      </Button>
      {result && result.ok && (
        <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          <CheckCircle2 className="h-4 w-4" />
          Активировано! Добавлено дней: {result.added_days}.
        </div>
      )}
      {result && !result.ok && <p className="text-sm text-destructive">{result.message}</p>}
    </form>
  );
}
