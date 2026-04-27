import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ExternalLink, Smartphone } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyButton } from "@/components/cabinet/copy-button";
import { PageHeader } from "@/components/cabinet/page-header";
import { api, type Instruction } from "@/lib/api";
import { getServerCookieHeader, requireAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";

const VALID = new Set(["ios", "android", "macos", "windows", "linux", "tv", "appletv"]);

type Params = Promise<{ platform: string }>;

export default async function PlatformInstallPage({ params }: { params: Params }) {
  await requireAuth();
  const { platform } = await params;
  if (!VALID.has(platform)) {
    notFound();
  }

  const cookieHeader = await getServerCookieHeader();
  let instruction: Instruction | null = null;
  try {
    instruction = await api.get<Instruction>(`/api/instructions/${platform}`, { cookieHeader });
  } catch {
    instruction = null;
  }

  if (!instruction) {
    return (
      <div className="space-y-6">
        <PageHeader title="Не удалось загрузить инструкцию" />
        <p className="text-sm text-muted-foreground">
          Попробуйте обновить страницу или вернуться позже.
        </p>
      </div>
    );
  }

  const subscriptionUrl = instruction.subscription_url || "";
  const deeplink = instruction.deeplink || "";
  const appLinks = collectAppLinks(instruction.app);

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit">
        <Link href="/cabinet/install">
          <ArrowLeft className="h-4 w-4" />
          К списку платформ
        </Link>
      </Button>
      <PageHeader title={instruction.title} description={`Приложение: ${instruction.app.name}.`} />

      <div className="grid gap-6 lg:grid-cols-[1fr_auto]">
        <Card>
          <CardHeader>
            <CardTitle>Шаги установки</CardTitle>
            <CardDescription>Выполните по порядку — занимает 1–2 минуты.</CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="space-y-4">
              {instruction.steps.map((step, idx) => (
                <li key={step.title} className="flex gap-4">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
                    {idx + 1}
                  </span>
                  <div>
                    <p className="font-medium">{step.title}</p>
                    {step.description && (
                      <p className="text-sm text-muted-foreground">{step.description}</p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>

        {instruction.qr_data_url && (
          <div className="flex h-fit flex-col items-center gap-2 self-start rounded-2xl bg-white p-4 shadow-lg shadow-black/20">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={instruction.qr_data_url}
              alt="QR подключение"
              className="h-44 w-44 rounded-xl"
            />
            <span className="text-[11px] font-medium text-black/70">Сканируйте в Happ</span>
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Подключение и приложение</CardTitle>
          <CardDescription>Кнопки автоматически открывают конфигурацию в Happ или ведут в магазин.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <Button asChild size="lg" variant="gradient" disabled={!deeplink}>
            <a href={deeplink || "#"} target="_blank" rel="noopener noreferrer">
              <Smartphone className="h-4 w-4" />
              Импортировать в приложение
            </a>
          </Button>
          {appLinks.map((link) => (
            <Button asChild key={link.label} size="lg" variant="outline">
              <a href={link.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4" />
                {link.label}
              </a>
            </Button>
          ))}
          <div className="sm:col-span-2 flex flex-col gap-2">
            <code className="block w-full truncate rounded-xl bg-muted/40 px-4 py-3 text-xs font-mono">
              {subscriptionUrl || "Подписка появится после первого входа в систему."}
            </code>
            {subscriptionUrl && <CopyButton value={subscriptionUrl} label="Копировать ссылку" />}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function collectAppLinks(app: Instruction["app"]): { label: string; url: string }[] {
  const out: { label: string; url: string }[] = [];
  if (app.store_url) out.push({ label: `${app.name} в App Store`, url: app.store_url });
  if (app.store_url_ru) out.push({ label: `${app.name} (RU)`, url: app.store_url_ru });
  if (app.apk_url) out.push({ label: "APK с GitHub", url: app.apk_url });
  if (app.download_url) out.push({ label: "Скачать установщик", url: app.download_url });
  if (app.deb_url) out.push({ label: "DEB-пакет", url: app.deb_url });
  return out;
}
