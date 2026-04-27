import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { SignupFlow } from "@/components/auth/signup-flow";
import { redirectIfAuthed } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function SignupPage() {
  await redirectIfAuthed();

  return (
    <AuthShell
      title="Регистрация"
      subtitle="Шаг 1 — привяжите Telegram, шаг 2 — подтвердите email."
      footer={
        <span>
          Уже есть аккаунт?{" "}
          <Link href="/auth/signin" className="text-primary underline-offset-4 hover:underline">
            Войти
          </Link>
        </span>
      }
    >
      <SignupFlow />
    </AuthShell>
  );
}
