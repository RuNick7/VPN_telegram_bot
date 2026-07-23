"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, CalendarDays, Gauge, Globe } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { type SubscriptionSnapshot } from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/utils";

import { ConnectButton } from "./connect-button";

const MAX_DAYS_FOR_BAR = 365;

export function SubscriptionCard({
  subscription,
  lteRemainingBytes,
}: {
  subscription: SubscriptionSnapshot | null;
  lteRemainingBytes: number;
}) {
  const days = subscription?.days_left ?? 0;
  const active = subscription?.is_active && days > 0;
  const subscriptionUrl = subscription?.subscription_url || "";
  const qr = subscription?.qr_data_url || null;

  return (
    <Card className="relative overflow-hidden border-primary/30 bg-card/80 shadow-xl shadow-primary/10">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_60%_at_30%_-10%,color-mix(in_oklab,var(--aurora-from)_30%,transparent),transparent)]" />
      <CardHeader className="relative">
        <div className="flex items-center gap-2">
          <Badge variant={active ? "success" : "warn"}>
            {active ? "Активна" : "Не активна"}
          </Badge>
          {!subscription?.panel_user_exists && (
            <Badge variant="muted">Профиль создаётся</Badge>
          )}
        </div>
        <CardTitle className="mt-2 flex items-end gap-2 text-3xl font-semibold">
          {days}
          <span className="text-base font-normal text-muted-foreground">дней осталось</span>
        </CardTitle>
        <CardDescription>
          {active
            ? "Подписка активна — пользуйтесь всеми серверами и протоколами."
            : "Подписка неактивна. Вы по-прежнему можете включать LTE-режим."}
        </CardDescription>
      </CardHeader>
      <CardContent className="relative grid gap-6 lg:grid-cols-[1fr_auto] lg:items-end">
        <div className="space-y-5">
          <div>
            <Progress value={Math.min(100, (days / MAX_DAYS_FOR_BAR) * 100)} className="h-2" />
            <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <CalendarDays className="h-3.5 w-3.5" />
                Истекает {formatDate(subscription?.subscription_ends || null)}
              </span>
              <span className="inline-flex items-center gap-1">
                <Gauge className="h-3.5 w-3.5" />
                LTE: {formatBytes(lteRemainingBytes)}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <ConnectButton subscriptionUrl={subscriptionUrl} />
            <Button asChild variant="outline" size="lg">
              <Link href="/cabinet/pay">
                Продлить подписку
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Globe className="h-3.5 w-3.5" />
            <span className="font-mono break-all">{subscriptionUrl || "Подключение появится после первого входа."}</span>
          </div>
        </div>
        {qr && (
          <div className="flex h-fit w-fit flex-col items-center gap-2 self-end rounded-2xl bg-white p-4 shadow-lg shadow-black/20">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={qr} alt="QR-код подключения" className="h-44 w-44 rounded-xl" />
            <span className="text-[11px] font-medium text-black/70">Сканируйте в Happ</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
