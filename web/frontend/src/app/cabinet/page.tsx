import Link from "next/link";
import { ArrowRight, CreditCard, Gauge, Server, Users } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SubscriptionCard } from "@/components/cabinet/subscription-card";
import { InstallPrompt } from "@/components/common/install-prompt";
import { NotificationsCard } from "@/components/cabinet/notifications-card";
import { api, type SubscriptionSnapshot } from "@/lib/api";
import { getServerCookieHeader, requireAuth } from "@/lib/auth";
import { formatBytes } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function CabinetOverviewPage() {
  const me = await requireAuth();
  const cookieHeader = await getServerCookieHeader();

  let subscription: SubscriptionSnapshot | null = me.subscription;
  try {
    subscription = await api.get<SubscriptionSnapshot>("/api/subscription", { cookieHeader });
  } catch {
    subscription = me.subscription;
  }

  const referredPeople = me.referrals.referred_people;
  const lteBytes = me.lte_remaining_bytes;

  const tiles = [
    {
      icon: CreditCard,
      title: "Оплата и тарифы",
      description: "Выберите срок подписки и оплатите через ЮKassa.",
      href: "/cabinet/pay",
    },
    {
      icon: Gauge,
      title: "LTE гигабайты",
      description: "Покупайте трафик пачками — для мобильного интернета.",
      href: "/cabinet/lte",
    },
    {
      icon: Server,
      title: "Серверы",
      description: "Список всех доступных локаций Remnawave.",
      href: "/cabinet/servers",
    },
    {
      icon: Users,
      title: "Рефералы",
      description: `Приглашено ${referredPeople}. Делитесь ссылкой и получайте бонусы.`,
      href: "/cabinet/referrals",
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">
          Привет, {me.first_name || me.username || "пользователь"}!
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Это ваш персональный кабинет. Здесь можно продлить подписку, купить LTE-гигабайты,
          посмотреть серверы и поделиться ссылкой с друзьями.
        </p>
      </div>

      <InstallPrompt />

      <SubscriptionCard subscription={subscription} lteRemainingBytes={lteBytes} />

      <NotificationsCard />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {tiles.map(({ icon: Icon, title, description, href }) => (
          <Link key={href} href={href} className="group">
            <Card className="h-full transition-transform duration-300 hover:-translate-y-1">
              <CardHeader>
                <div className="mb-3 grid h-10 w-10 place-items-center rounded-xl bg-primary/15 text-primary">
                  <Icon className="h-5 w-5" />
                </div>
                <CardTitle className="text-base">{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
              <CardContent>
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors group-hover:text-foreground">
                  Открыть <ArrowRight className="h-3 w-3" />
                </span>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Текущий аккаунт</CardTitle>
          <CardDescription>Эти данные используются ботом и сайтом совместно.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 text-sm sm:grid-cols-2">
          <Row label="Email" value={me.email || "не привязан"} />
          <Row label="Telegram ID" value={me.telegram_id?.toString() ?? "—"} mono />
          <Row label="Username" value={me.username ? `@${me.username}` : "—"} mono />
          <Row label="LTE остаток" value={formatBytes(lteBytes)} />
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-muted/40 px-4 py-3">
      <span className="text-muted-foreground">{label}</span>
      <span className={mono ? "font-mono" : "font-medium"}>{value}</span>
    </div>
  );
}
