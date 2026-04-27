import Link from "next/link";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

const FAQ_URL = process.env.NEXT_PUBLIC_FAQ_URL || "https://kairavpn.pro/faq";

const ITEMS = [
  {
    q: "Как работает passwordless вход?",
    a: "Мы не храним пароли. После регистрации мы отправляем одноразовую ссылку на email. Перейдя по ней, вы попадаете в кабинет — данные защищены httpOnly cookie с коротким сроком жизни.",
  },
  {
    q: "Зачем привязывать Telegram?",
    a: "Telegram-аккаунт — это второй фактор владения. Через бота приходят уведомления о подписке и платежах, а также именно с ним связаны серверы и баланс трафика.",
  },
  {
    q: "Что такое LTE-режим?",
    a: "Это пакеты гигабайтов, которые вы можете покупать поверх обычной подписки. Удобно, если хотите включать VPN ситуативно — он расходует только купленный трафик.",
  },
  {
    q: "Можно ли пользоваться без подписки?",
    a: "Да, при первой регистрации мы дарим пробный период. После его окончания доступ остаётся к LTE-серверам, если у вас есть пакет гигабайтов.",
  },
];

export function Faq() {
  return (
    <section id="faq" className="relative mx-auto w-full max-w-3xl px-4 py-20 md:px-6">
      <div className="mb-12 text-center">
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Частые вопросы</h2>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
          Не нашли свой вопрос? Загляните в{" "}
          <Link href={FAQ_URL} className="text-primary underline-offset-4 hover:underline" target="_blank" rel="noreferrer">
            полный FAQ
          </Link>{" "}
          — там собраны решения для всех ОС.
        </p>
      </div>
      <Accordion type="single" collapsible className="space-y-3">
        {ITEMS.map((item, idx) => (
          <AccordionItem key={item.q} value={`item-${idx}`}>
            <AccordionTrigger>{item.q}</AccordionTrigger>
            <AccordionContent>{item.a}</AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  );
}
