import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/cabinet/page-header";
import { PaymentLauncher } from "@/components/cabinet/payment-launcher";
import { api, type GiftTariffsResponse } from "@/lib/api";
import { getServerCookieHeader, requireAuth } from "@/lib/auth";
import { formatPrice } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function CabinetGiftsPage() {
  await requireAuth();
  const cookieHeader = await getServerCookieHeader();
  let payload: GiftTariffsResponse = { tariffs: [] };
  try {
    payload = await api.get<GiftTariffsResponse>("/api/gifts/tariffs", { cookieHeader });
  } catch {
    // ignore
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Подарите подписку"
        description="После оплаты вы получите промокод. Перешлите его другу — при активации он получит выбранный срок подписки."
      />
      {payload.tariffs.length === 0 ? (
        <div className="rounded-2xl border border-border/60 bg-card/40 p-8 text-center text-sm text-muted-foreground">
          Подарочные тарифы временно недоступны.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {payload.tariffs.map((tariff) => (
            <Card key={tariff.months}>
              <CardHeader>
                <CardTitle className="text-xl">{tariff.months} мес.</CardTitle>
                <CardDescription>{tariff.days} дней доступа</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-semibold">{formatPrice(tariff.price)}</span>
                  <span className="text-sm text-muted-foreground">₽</span>
                </div>
                <PaymentLauncher
                  endpoint="/api/gifts/buy"
                  body={{ months: tariff.months }}
                  label="Подарить"
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
