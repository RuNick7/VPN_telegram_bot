import { CabinetBottomNav, CabinetSidebar } from "@/components/cabinet/cabinet-nav";
import { CabinetTopbar } from "@/components/cabinet/cabinet-topbar";
import { requireAuth } from "@/lib/auth";

export default async function CabinetLayout({ children }: { children: React.ReactNode }) {
  const me = await requireAuth();
  return (
    <div className="flex min-h-screen">
      <CabinetSidebar email={me.email} telegramId={me.telegram_id} />
      <div className="flex w-full flex-1 flex-col">
        <CabinetTopbar email={me.email} />
        <main className="aurora-bg relative flex-1 overflow-x-hidden">
          <div className="relative z-10 mx-auto w-full max-w-5xl px-4 py-8 md:px-8">{children}</div>
        </main>
        <CabinetBottomNav />
      </div>
    </div>
  );
}
