import { Globe, Gauge, ShieldCheck, Smartphone, Sparkles, Wifi } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const FEATURES = [
  {
    icon: Gauge,
    title: "Молниеносная скорость",
    text: "Современные протоколы и оптимизированные серверы — без потерь скорости и пинга.",
  },
  {
    icon: Globe,
    title: "Серверы по миру",
    text: "Десятки локаций для бесшовного доступа к стримингам, играм и рабочим сервисам.",
  },
  {
    icon: Wifi,
    title: "LTE-режим",
    text: "Покупайте только нужный трафик в гигабайтах — идеально для мобильного интернета.",
  },
  {
    icon: ShieldCheck,
    title: "Без логов",
    text: "Мы не храним пароли и не записываем историю — приватность по умолчанию.",
  },
  {
    icon: Smartphone,
    title: "Любая платформа",
    text: "iOS, Android, macOS, Windows, Linux, Smart TV — установка в один клик.",
  },
  {
    icon: Sparkles,
    title: "Подарки и бонусы",
    text: "Делитесь подпиской с друзьями и получайте скидки за приглашения.",
  },
];

export function Features() {
  return (
    <section id="features" className="relative mx-auto w-full max-w-6xl px-4 py-20 md:px-6">
      <div className="mb-12 text-center">
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
          Всё, что нужно для жизни без блокировок
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">
          Один тариф — все возможности. Кабинет на сайте полностью повторяет функциональность
          Telegram-бота и работает с теми же серверами.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <Card key={title} className="group transition-transform duration-300 hover:-translate-y-1">
            <CardHeader>
              <div className="mb-3 grid h-11 w-11 place-items-center rounded-xl bg-primary/15 text-primary">
                <Icon className="h-5 w-5" />
              </div>
              <CardTitle>{title}</CardTitle>
              <CardDescription>{text}</CardDescription>
            </CardHeader>
            <CardContent />
          </Card>
        ))}
      </div>
    </section>
  );
}
