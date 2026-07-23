"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  CreditCard,
  Gauge,
  Gift,
  Home,
  LogOut,
  Server,
  Sparkles,
  Tag,
  Ticket,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";

type Item = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
};

const NAV: Item[] = [
  { href: "/cabinet", label: "Обзор", icon: Home },
  { href: "/cabinet/pay", label: "Тарифы", icon: CreditCard },
  { href: "/cabinet/lte", label: "LTE", icon: Gauge },
  { href: "/cabinet/gifts", label: "Подарки", icon: Gift },
  { href: "/cabinet/promo", label: "Промокод", icon: Ticket },
  { href: "/cabinet/referrals", label: "Рефералы", icon: Users },
  { href: "/cabinet/servers", label: "Серверы", icon: Server },
  { href: "/cabinet/install", label: "Установка", icon: Tag },
];

export function CabinetSidebar({ email, telegramId }: { email: string | null; telegramId: number | null }) {
  const pathname = usePathname();
  return (
    <aside className="hidden w-64 shrink-0 border-r border-border/50 bg-background/60 backdrop-blur md:flex md:flex-col">
      <div className="flex h-16 items-center gap-2 border-b border-border/40 px-6 font-semibold">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-[linear-gradient(135deg,var(--aurora-from),var(--aurora-to))] text-primary-foreground shadow-lg shadow-primary/30">
          <Sparkles className="h-4 w-4" />
        </span>
        <span>
          Kaira<span className="gradient-text">VPN</span>
        </span>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active =
            item.href === "/cabinet" ? pathname === "/cabinet" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-primary/10 text-foreground shadow-inner shadow-primary/10"
                  : "text-muted-foreground hover:bg-card hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border/40 px-4 py-4 text-xs text-muted-foreground">
        <div className="truncate text-foreground">{email || "Без email"}</div>
        <div className="font-mono text-[11px]">TG ID: {telegramId ?? "—"}</div>
        <Link
          href="/auth/signout"
          className="mt-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <LogOut className="h-3.5 w-3.5" />
          Выйти
        </Link>
      </div>
    </aside>
  );
}

export function CabinetBottomNav() {
  const pathname = usePathname();
  const items = NAV.slice(0, 5);
  return (
    <nav className="sticky bottom-0 z-20 flex border-t border-border/50 bg-background/80 backdrop-blur md:hidden">
      {items.map((item) => {
        const Icon = item.icon;
        const active =
          item.href === "/cabinet" ? pathname === "/cabinet" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex flex-1 flex-col items-center justify-center gap-1 py-2 text-[11px] transition-colors",
              active ? "text-primary" : "text-muted-foreground",
            )}
          >
            <Icon className="h-5 w-5" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
