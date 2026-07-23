import Link from "next/link";
import { Sparkles } from "lucide-react";

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="aurora-bg relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div className="relative z-10 w-full max-w-md">
        <Link href="/" className="mb-8 inline-flex items-center gap-2 font-semibold">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-[linear-gradient(135deg,var(--aurora-from),var(--aurora-to))] text-primary-foreground shadow-lg shadow-primary/30">
            <Sparkles className="h-4 w-4" />
          </span>
          <span className="text-base tracking-tight">
            Kaira<span className="gradient-text">VPN</span>
          </span>
        </Link>
        <div className="glass-strong rounded-3xl p-8 shadow-2xl shadow-primary/10">
          <h1 className="mb-1 text-2xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="mb-6 text-sm text-muted-foreground">{subtitle}</p>}
          {children}
        </div>
        {footer && <div className="mt-6 text-center text-sm text-muted-foreground">{footer}</div>}
      </div>
    </div>
  );
}
