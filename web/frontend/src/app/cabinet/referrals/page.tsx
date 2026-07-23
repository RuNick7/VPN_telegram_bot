import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyButton } from "@/components/cabinet/copy-button";
import { PageHeader } from "@/components/cabinet/page-header";
import { ReferrerForm } from "@/components/cabinet/referrer-form";
import { api, type ReferralOverview } from "@/lib/api";
import { getServerCookieHeader, requireAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function CabinetReferralsPage() {
  await requireAuth();
  const cookieHeader = await getServerCookieHeader();
  let overview: ReferralOverview = {
    referred_people: 0,
    telegram_tag: null,
    referrer_tag: null,
    gifted_subscriptions: 0,
    share_link: null,
  };
  try {
    overview = await api.get<ReferralOverview>("/api/referrals", { cookieHeader });
  } catch {
    // ignore
  }

  const shareLink = overview.share_link || "";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Реферальная программа"
        description="Приглашайте друзей и получайте скидку на подписку. Подарочные подписки увеличивают вашу статистику."
      />
      <div className="grid gap-4 md:grid-cols-3">
        <Stat label="Приглашено друзей" value={String(overview.referred_people)} />
        <Stat label="Подарочных подписок" value={String(overview.gifted_subscriptions ?? 0)} />
        <Stat label="Ваш Telegram-ник" value={overview.telegram_tag ? `@${overview.telegram_tag}` : "—"} mono />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Ваша реферальная ссылка</CardTitle>
          <CardDescription>
            Делитесь этой ссылкой — каждый, кто перейдёт по ней и оплатит подписку, принесёт вам скидку.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <code className="flex-1 truncate rounded-xl bg-muted/40 px-4 py-3 text-sm font-mono">
            {shareLink || "Ссылка появится после привязки Telegram"}
          </code>
          <CopyButton value={shareLink} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Кто вас пригласил</CardTitle>
          <CardDescription>Если ваш друг уже пользуется KairaVPN — укажите его ник, чтобы он получил бонус.</CardDescription>
        </CardHeader>
        <CardContent>
          <ReferrerForm existingTag={overview.referrer_tag || null} />
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className={mono ? "font-mono text-2xl" : "text-2xl"}>{value}</CardTitle>
      </CardHeader>
      <CardContent />
    </Card>
  );
}
