import { PageHeader } from "@/components/cabinet/page-header";
import { TariffGrid } from "@/components/cabinet/tariff-grid";
import { api, type TariffsResponse } from "@/lib/api";
import { getServerCookieHeader, requireAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function CabinetPayPage() {
  await requireAuth();
  const cookieHeader = await getServerCookieHeader();
  let payload: TariffsResponse = { referred_people: 0, tariffs: [] };
  try {
    payload = await api.get<TariffsResponse>("/api/subscription/tariffs", { cookieHeader });
  } catch {
    // ignore — show empty state
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Тарифы и оплата"
        description="Чем больше срок, тем выгоднее цена. Оплата проходит через ЮKassa, после успеха подписка активируется автоматически."
      />
      {payload.tariffs.length > 0 ? (
        <TariffGrid tariffs={payload.tariffs} referredPeople={payload.referred_people} />
      ) : (
        <div className="rounded-2xl border border-border/60 bg-card/40 p-8 text-center text-sm text-muted-foreground">
          Не удалось загрузить тарифы. Попробуйте обновить страницу.
        </div>
      )}
    </div>
  );
}
