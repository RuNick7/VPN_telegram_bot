import { AuthShell } from "@/components/auth/auth-shell";
import { MagicVerify } from "@/components/auth/magic-verify";

export const dynamic = "force-dynamic";

type SearchParams = Promise<{ token?: string }>;

export default async function MagicPage({ searchParams }: { searchParams: SearchParams }) {
  const { token } = await searchParams;
  return (
    <AuthShell title="Вход в кабинет" subtitle="Проверяем ссылку и подписываем сессию.">
      <MagicVerify token={token || ""} />
    </AuthShell>
  );
}
