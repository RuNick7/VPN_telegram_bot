import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/cabinet/page-header";
import { PaymentLauncher } from "@/components/cabinet/payment-launcher";
import { api, type LtePackagesResponse } from "@/lib/api";
import { getServerCookieHeader, requireAuth } from "@/lib/auth";
import { formatBytes, formatPrice } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function CabinetLtePage() {
  const me = await requireAuth();
  const cookieHeader = await getServerCookieHeader();
  let payload: LtePackagesResponse = { packages: [] };
  try {
    payload = await api.get<LtePackagesResponse>("/api/lte/packages", { cookieHeader });
  } catch {
    // ignore
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="LTE гигабайты"
        description={`Покупайте трафик пачками — он расходуется только при подключении в LTE-режиме. Сейчас доступно ${formatBytes(me.lte_remaining_bytes)}.`}
      />
      <Card className="border-primary/30 bg-card/80">
        <CardHeader>
          <CardTitle>Текущий баланс</CardTitle>
          <CardDescription>
            Это объём трафика, который сейчас вам доступен (включая бесплатные ГБ за тариф).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-semibold">{formatBytes(me.lte_remaining_bytes)}</span>
            <span className="text-sm text-muted-foreground">осталось</span>
          </div>
        </CardContent>
      </Card>

      {payload.packages.length === 0 ? (
        <div className="rounded-2xl border border-border/60 bg-card/40 p-8 text-center text-sm text-muted-foreground">
          Пакеты LTE временно недоступны.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {payload.packages.map((pkg) => (
            <Card key={pkg.gb}>
              <CardHeader>
                <CardTitle className="text-2xl">{pkg.gb} ГБ</CardTitle>
                <CardDescription>Идеально для краткосрочного использования.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-semibold">{formatPrice(pkg.price)}</span>
                  <span className="text-sm text-muted-foreground">₽</span>
                </div>
                <PaymentLauncher
                  endpoint="/api/lte/buy"
                  body={{ gb: pkg.gb }}
                  label="Купить пакет"
                  variant="gradient"
                />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
