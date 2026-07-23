"use client";

import * as React from "react";
import Link from "next/link";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type ApiError, type PaymentSnapshot } from "@/lib/api";

const POLL_INTERVAL = 3000;
const MAX_ATTEMPTS = 40;

type Stage = "polling" | "succeeded" | "failed" | "timeout";

export function PaymentPoller({ paymentId: initialPaymentId }: { paymentId: string }) {
  const [stage, setStage] = React.useState<Stage>("polling");
  const [payment, setPayment] = React.useState<PaymentSnapshot | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [paymentId, setPaymentId] = React.useState(initialPaymentId);

  React.useEffect(() => {
    if (paymentId) return;
    if (typeof window === "undefined") return;
    try {
      const raw = sessionStorage.getItem("kaira:last_payment");
      if (raw) {
        const parsed = JSON.parse(raw) as { payment_id?: string };
        if (parsed.payment_id) setPaymentId(parsed.payment_id);
      }
    } catch {
      // ignore
    }
  }, [paymentId]);

  React.useEffect(() => {
    if (!paymentId) {
      setStage("failed");
      setError("Платёж не найден.");
      return;
    }
    let attempts = 0;
    let cancelled = false;
    const tick = async () => {
      attempts += 1;
      try {
        const snapshot = await api.get<PaymentSnapshot>(`/api/payments/${encodeURIComponent(paymentId)}`);
        if (cancelled) return;
        setPayment(snapshot);
        if (snapshot.status === "succeeded" || snapshot.local_status === "succeeded") {
          setStage("succeeded");
          return;
        }
        if (["canceled", "failed"].includes(snapshot.status.toLowerCase())) {
          setStage("failed");
          setError("Платёж был отменён или не прошёл.");
          return;
        }
        if (attempts >= MAX_ATTEMPTS) {
          setStage("timeout");
        }
      } catch (err) {
        if (cancelled) return;
        setError((err as ApiError).detail || "Не удалось проверить платёж.");
      }
    };
    void tick();
    const id = setInterval(() => {
      if (stage === "polling") void tick();
    }, POLL_INTERVAL);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [paymentId, stage]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <StageIcon stage={stage} />
          {stageTitle(stage)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="rounded-xl bg-muted/40 p-4 font-mono text-xs text-muted-foreground">
          payment_id: {paymentId || "—"}
          {payment && (
            <>
              <br />
              status: {payment.status || payment.local_status || "—"}
            </>
          )}
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline">
            <Link href="/cabinet">Вернуться в кабинет</Link>
          </Button>
          {stage === "failed" && (
            <Button asChild variant="gradient">
              <Link href="/cabinet/pay">Попробовать снова</Link>
            </Button>
          )}
          {stage === "timeout" && (
            <Button onClick={() => location.reload()}>Проверить ещё раз</Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function StageIcon({ stage }: { stage: Stage }) {
  if (stage === "succeeded") return <CheckCircle2 className="h-5 w-5 text-emerald-400" />;
  if (stage === "failed") return <XCircle className="h-5 w-5 text-destructive" />;
  return <Loader2 className="h-5 w-5 animate-spin text-primary" />;
}

function stageTitle(stage: Stage): string {
  switch (stage) {
    case "succeeded":
      return "Платёж получен — подписка активирована";
    case "failed":
      return "Платёж не прошёл";
    case "timeout":
      return "Долго не приходит подтверждение";
    default:
      return "Ожидаем подтверждение от ЮKassa";
  }
}
