"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, Loader2, Mail, MessageCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  api,
  type ApiError,
  type TelegramLinkStart,
  type TelegramLinkStatus,
} from "@/lib/api";

type Step = "telegram" | "email" | "sent";

const POLL_INTERVAL_MS = 2500;

export function SignupFlow() {
  const router = useRouter();
  const [step, setStep] = React.useState<Step>("telegram");
  const [link, setLink] = React.useState<TelegramLinkStart | null>(null);
  const [status, setStatus] = React.useState<TelegramLinkStatus["status"]>("pending");
  const [issuing, setIssuing] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [email, setEmail] = React.useState("");

  const startTelegram = React.useCallback(async () => {
    setIssuing(true);
    setError(null);
    try {
      const data = await api.post<TelegramLinkStart>("/api/auth/telegram/start");
      setLink(data);
      setStatus("pending");
    } catch (err) {
      setError((err as ApiError).detail || "Не удалось получить ссылку");
    } finally {
      setIssuing(false);
    }
  }, []);

  React.useEffect(() => {
    void startTelegram();
  }, [startTelegram]);

  React.useEffect(() => {
    if (!link || status === "confirmed") return;
    let cancelled = false;
    const tick = async () => {
      try {
        const data = await api.get<TelegramLinkStatus>(
          `/api/auth/telegram/status?token=${encodeURIComponent(link.token)}`,
        );
        if (cancelled) return;
        setStatus(data.status);
        if (data.status === "confirmed") {
          setStep("email");
        } else if (data.status === "expired") {
          setError("Срок действия ссылки истёк, обновите страницу.");
        }
      } catch {
        // ignore polling errors
      }
    };
    const id = setInterval(tick, POLL_INTERVAL_MS);
    void tick();
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [link, status]);

  const submitEmail = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!link) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/api/auth/email/signup", { email: email.trim(), link_token: link.token });
      setStep("sent");
    } catch (err) {
      setError((err as ApiError).detail || "Не удалось отправить письмо");
    } finally {
      setSubmitting(false);
    }
  };

  if (step === "sent") {
    return (
      <div className="flex flex-col items-center gap-4 py-4 text-center">
        <div className="grid h-12 w-12 place-items-center rounded-full bg-emerald-500/15 text-emerald-400">
          <Mail className="h-6 w-6" />
        </div>
        <div>
          <p className="text-base font-medium">Проверьте почту</p>
          <p className="text-sm text-muted-foreground">
            Мы отправили ссылку для входа на <span className="font-mono text-foreground">{email}</span>.
            Перейдите по ней — она действительна 15 минут.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => router.push("/auth/signin")}>
          Уже подтвердили? Войти
        </Button>
      </div>
    );
  }

  if (step === "email") {
    return (
      <form onSubmit={submitEmail} className="flex flex-col gap-5">
        <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          <CheckCircle2 className="h-5 w-5 shrink-0" />
          <span>Telegram привязан. Осталось подтвердить email.</span>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="email">Email для входа</Label>
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
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" size="lg" variant="gradient" disabled={submitting || !email.trim()}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
          Получить ссылку
        </Button>
      </form>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm text-muted-foreground">
        Откройте Telegram-бота — мы свяжем учётную запись и автоматически продолжим
        регистрацию здесь, без паролей.
      </p>
      <div className="flex flex-col items-center gap-3 rounded-2xl border border-border/60 bg-card/40 p-6">
        <Badge variant={status === "expired" ? "warn" : "info"}>
          {status === "expired" ? "Ссылка истекла" : "Ожидание подтверждения"}
        </Badge>
        <Button
          asChild
          size="lg"
          variant="gradient"
          className="w-full"
          disabled={!link?.deeplink || issuing}
        >
          <a href={link?.deeplink || "#"} target="_blank" rel="noopener noreferrer">
            <MessageCircle className="h-4 w-4" />
            Открыть Telegram
          </a>
        </Button>
        <Button variant="ghost" size="sm" onClick={startTelegram} disabled={issuing}>
          {issuing ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Получить новую ссылку
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <p className="text-center text-xs text-muted-foreground">
        После подтверждения мы автоматически перейдём к следующему шагу.
      </p>
    </div>
  );
}
