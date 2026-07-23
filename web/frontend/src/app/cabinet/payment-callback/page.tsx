import { PageHeader } from "@/components/cabinet/page-header";
import { PaymentPoller } from "@/components/cabinet/payment-poller";
import { requireAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";

type SearchParams = Promise<{ payment_id?: string }>;

export default async function PaymentCallbackPage({ searchParams }: { searchParams: SearchParams }) {
  await requireAuth();
  const { payment_id } = await searchParams;
  return (
    <div className="space-y-6">
      <PageHeader
        title="Проверяем платёж"
        description="Подождите немного — мы убедимся, что оплата прошла, и активируем подписку."
      />
      <PaymentPoller paymentId={payment_id || ""} />
    </div>
  );
}
