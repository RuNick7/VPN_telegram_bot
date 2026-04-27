import Link from "next/link";
import { LogOut, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";

export function CabinetTopbar({ email }: { email: string | null }) {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border/40 bg-background/70 px-4 backdrop-blur md:hidden">
      <Link href="/cabinet" className="flex items-center gap-2 font-semibold">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-[linear-gradient(135deg,var(--aurora-from),var(--aurora-to))] text-primary-foreground shadow-lg shadow-primary/30">
          <Sparkles className="h-3.5 w-3.5" />
        </span>
        <span className="text-sm">
          Kaira<span className="gradient-text">VPN</span>
        </span>
      </Link>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="hidden max-w-[140px] truncate sm:inline">{email}</span>
        <Button asChild size="icon" variant="ghost">
          <Link href="/auth/signout">
            <LogOut className="h-4 w-4" />
          </Link>
        </Button>
      </div>
    </header>
  );
}
