import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { SignInForm } from "@/components/auth/signin-form";
import { redirectIfAuthed } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function SignInPage() {
  await redirectIfAuthed();
  return (
    <AuthShell
      title="Вход"
      subtitle="Введите email — мы отправим одноразовую ссылку для входа без пароля."
      footer={
        <span>
          Ещё нет аккаунта?{" "}
          <Link href="/auth/signup" className="text-primary underline-offset-4 hover:underline">
            Зарегистрироваться
          </Link>
        </span>
      }
    >
      <SignInForm />
    </AuthShell>
  );
}
