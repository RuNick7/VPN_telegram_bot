import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/cabinet/page-header";
import { PromoForm } from "@/components/cabinet/promo-form";
import { requireAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function CabinetPromoPage() {
  await requireAuth();
  return (
    <div className="space-y-6">
      <PageHeader title="Промокод" description="Активируйте подарочный код или промокод на дополнительные дни." />
      <Card className="max-w-md">
        <CardHeader>
          <CardTitle>Активация промокода</CardTitle>
          <CardDescription>Введите код, который вам прислали — мы автоматически продлим подписку.</CardDescription>
        </CardHeader>
        <CardContent>
          <PromoForm />
        </CardContent>
      </Card>
    </div>
  );
}
