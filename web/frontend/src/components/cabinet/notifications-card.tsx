"use client";

import { Bell, BellOff, Loader2, ShieldAlert, ShieldOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { usePushSubscription } from "@/hooks/use-push-subscription";

export function NotificationsCard() {
  const { status, error, busy, subscribe, unsubscribe } = usePushSubscription();

  if (status === "loading") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Bell className="h-4 w-4" /> Уведомления
          </CardTitle>
          <CardDescription>Проверяем поддержку браузера…</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (status === "unsupported") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <BellOff className="h-4 w-4" /> Уведомления
          </CardTitle>
          <CardDescription>
            В этом браузере push-уведомления не поддерживаются. На iPhone обновите iOS
            до 16.4+ и установите KairaVPN на главный экран. Все важные события
            продолжат приходить в Telegram.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (status === "blocked") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldOff className="h-4 w-4 text-amber-400" /> Уведомления отключены
          </CardTitle>
          <CardDescription>
            Вы запретили уведомления для этого сайта. Включить можно в настройках браузера
            (или Настройки → Уведомления → KairaVPN на iOS).
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (status === "unconfigured") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldAlert className="h-4 w-4 text-amber-400" /> Уведомления недоступны
          </CardTitle>
          <CardDescription>
            На сервере ещё не настроены push-ключи. Загляните позже — мы скоро включим.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const subscribed = status === "subscribed";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Bell className="h-4 w-4" /> Уведомления
        </CardTitle>
        <CardDescription>
          {subscribed
            ? "Включены. Будем сообщать об оплате, продлении и реферальных бонусах."
            : "Получайте моментальные сообщения о платежах, окончании подписки и реферальных бонусах прямо на устройство."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-3">
        {subscribed ? (
          <Button variant="outline" disabled={busy} onClick={() => void unsubscribe()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <BellOff className="h-4 w-4" />}
            Выключить уведомления
          </Button>
        ) : (
          <Button variant="gradient" disabled={busy} onClick={() => void subscribe()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}
            Включить уведомления
          </Button>
        )}
        {error ? <span className="text-xs text-destructive">{error}</span> : null}
      </CardContent>
    </Card>
  );
}
