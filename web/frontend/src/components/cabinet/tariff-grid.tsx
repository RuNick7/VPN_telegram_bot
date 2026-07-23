"use client";

import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type Tariff } from "@/lib/api";
import { cn, formatPrice } from "@/lib/utils";

import { PaymentLauncher } from "./payment-launcher";

const POPULAR_MONTHS = 3;

export function TariffGrid({ tariffs, referredPeople }: { tariffs: Tariff[]; referredPeople: number }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {tariffs.map((tariff) => (
          <TariffCard key={tariff.months} tariff={tariff} highlighted={tariff.months === POPULAR_MONTHS} />
        ))}
      </div>
      {referredPeople > 0 && (
        <p className="text-center text-xs text-muted-foreground">
          Цены показаны с учётом приглашённых вами друзей: {referredPeople}.
        </p>
      )}
    </div>
  );
}

function TariffCard({ tariff, highlighted }: { tariff: Tariff; highlighted?: boolean }) {
  return (
    <Card
      className={cn(
        "relative flex h-full flex-col",
        highlighted && "border-primary/60 bg-card/80 shadow-xl shadow-primary/15",
      )}
    >
      {highlighted && (
        <Badge className="absolute right-4 top-4" variant="default">
          Популярно
        </Badge>
      )}
      <CardHeader>
        <CardTitle className="text-xl">{tariff.months} мес.</CardTitle>
        <CardDescription>
          {tariff.discount_percent > 0
            ? `Скидка ${tariff.discount_percent}% от месячного`
            : "Базовая цена"}
        </CardDescription>
      </CardHeader>
      <CardContent className="mt-auto flex flex-col gap-4">
        <div>
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-semibold">{formatPrice(tariff.price)}</span>
            <span className="text-sm text-muted-foreground">₽</span>
          </div>
          {tariff.months > 1 && (
            <p className="text-xs text-muted-foreground">
              ≈ {formatPrice(tariff.monthly_equivalent)} ₽ / мес.
            </p>
          )}
        </div>
        <PaymentLauncher
          endpoint="/api/subscription/extend"
          body={{ months: tariff.months }}
          label="Оплатить"
          variant={highlighted ? "gradient" : "outline"}
        />
      </CardContent>
    </Card>
  );
}
