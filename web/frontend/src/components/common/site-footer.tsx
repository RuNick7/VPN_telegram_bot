import Link from "next/link";

const FAQ_URL = process.env.NEXT_PUBLIC_FAQ_URL || "https://kairavpn.pro/faq";

export function SiteFooter() {
  return (
    <footer className="border-t border-border/50 bg-background/70 py-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-4 px-4 text-sm text-muted-foreground md:flex-row md:px-6">
        <span>© {new Date().getFullYear()} KairaVPN. Все права защищены.</span>
        <nav className="flex flex-wrap items-center gap-4">
          <Link href={FAQ_URL} className="transition-colors hover:text-foreground" target="_blank" rel="noreferrer">
            FAQ
          </Link>
          <Link href="/auth/signin" className="transition-colors hover:text-foreground">
            Войти
          </Link>
          <Link href="/auth/signup" className="transition-colors hover:text-foreground">
            Регистрация
          </Link>
        </nav>
      </div>
    </footer>
  );
}
