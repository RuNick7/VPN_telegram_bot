import Link from "next/link";
import {
  Apple,
  Laptop,
  MonitorSmartphone,
  Smartphone,
  Tv,
  TvMinimalPlay,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/cabinet/page-header";
import { requireAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";

const PLATFORMS: { slug: string; title: string; subtitle: string; Icon: React.ComponentType<{ className?: string }> }[] = [
  { slug: "ios", title: "iPhone / iPad", subtitle: "iOS 16+", Icon: Smartphone },
  { slug: "android", title: "Android", subtitle: "Android 7+", Icon: MonitorSmartphone },
  { slug: "macos", title: "macOS", subtitle: "Apple Silicon / Intel", Icon: Apple },
  { slug: "windows", title: "Windows", subtitle: "10 и новее", Icon: Laptop },
  { slug: "linux", title: "Linux", subtitle: "NekoRay", Icon: Laptop },
  { slug: "tv", title: "Android TV", subtitle: "TV-приставки", Icon: Tv },
  { slug: "appletv", title: "Apple TV", subtitle: "tvOS 17+", Icon: TvMinimalPlay },
];

export default async function CabinetInstallIndex() {
  await requireAuth();
  return (
    <div className="space-y-6">
      <PageHeader
        title="Установка"
        description="Выберите платформу — мы покажем шаги, ссылки на приложение и QR-код подключения."
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {PLATFORMS.map((platform) => {
          const Icon = platform.Icon;
          return (
            <Link key={platform.slug} href={`/cabinet/install/${platform.slug}`} className="group">
              <Card className="h-full transition-transform duration-200 hover:-translate-y-1">
                <CardHeader>
                  <div className="mb-3 grid h-10 w-10 place-items-center rounded-xl bg-primary/15 text-primary">
                    <Icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-base">{platform.title}</CardTitle>
                  <CardDescription>{platform.subtitle}</CardDescription>
                </CardHeader>
                <CardContent />
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
