import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPrice } from "@/lib/utils";

type Plan = {
  months: number;
  price: number;
  popular?: boolean;
  description: string;
};

const PREVIEW_PLANS: Plan[] = [
  { months: 1, price: 199, description: "Идеально, чтобы попробовать" },
  { months: 3, price: 499, popular: true, description: "Самый популярный вариант" },
  { months: 6, price: 899, description: "Для постоянного использования" },
  { months: 12, price: 1599, description: "Максимальная экономия" },
];

export function PricingPreview() {
  return (
    <section id="pricing" className="relative mx-auto w-full max-w-6xl px-4 py-20 md:px-6">
      <div className="mb-12 text-center">
        <Badge variant="info" className="mx-auto mb-3">
          Прозрачные цены
        </Badge>
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Один тариф — все серверы</h2>
        <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">
          После регистрации внутри кабинета вы увидите ваши персональные цены: они зависят
          от количества приглашённых друзей и активных бонусов.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {PREVIEW_PLANS.map((plan) => (
          <Card
            key={plan.months}
            className={
              plan.popular
                ? "relative border-primary/60 bg-card/80 shadow-xl shadow-primary/10"
                : "relative"
            }
          >
            {plan.popular && (
              <Badge className="absolute right-4 top-4" variant="default">
                Популярно
              </Badge>
            )}
            <CardHeader>
              <CardTitle className="text-xl">{plan.months} мес.</CardTitle>
              <CardDescription>{plan.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex items-baseline gap-1">
                <span className="text-3xl font-semibold">{formatPrice(plan.price)}</span>
                <span className="text-sm text-muted-foreground">₽</span>
              </div>
              <Button asChild variant={plan.popular ? "gradient" : "outline"} className="w-full">
                <Link href="/auth/signup">Подключить</Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
