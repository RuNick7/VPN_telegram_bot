import Link from "next/link";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getMe } from "@/lib/auth";

export async function SiteHeader() {
  const me = await getMe();
  const isAuthed = Boolean(me);

  return (
    <header className="sticky top-0 z-30 border-b border-border/40 bg-background/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 md:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-[linear-gradient(135deg,var(--aurora-from),var(--aurora-to))] text-primary-foreground shadow-lg shadow-primary/30">
            <Sparkles className="h-4 w-4" />
          </span>
          <span className="text-base tracking-tight">
            Kaira<span className="gradient-text">VPN</span>
          </span>
        </Link>
        <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
          <Link href="/#features" className="transition-colors hover:text-foreground">
            Возможности
          </Link>
          <Link href="/#pricing" className="transition-colors hover:text-foreground">
            Тарифы
          </Link>
          <Link href="/#faq" className="transition-colors hover:text-foreground">
            FAQ
          </Link>
        </nav>
        <div className="flex items-center gap-2">
          {isAuthed ? (
            <Button asChild size="sm" variant="gradient">
              <Link href="/cabinet">Кабинет</Link>
            </Button>
          ) : (
            <>
              <Button asChild size="sm" variant="ghost" className="hidden md:inline-flex">
                <Link href="/auth/signin">Войти</Link>
              </Button>
              <Button asChild size="sm" variant="gradient">
                <Link href="/auth/signup">Начать</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
