import { Globe } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/cabinet/page-header";
import { api, type Server, type ServersResponse } from "@/lib/api";
import { getServerCookieHeader, requireAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function CabinetServersPage() {
  await requireAuth();
  const cookieHeader = await getServerCookieHeader();
  let payload: ServersResponse = { servers: [] };
  try {
    payload = await api.get<ServersResponse>("/api/servers", { cookieHeader });
  } catch {
    // ignore
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Серверы"
        description="Список доступных локаций. Если бейдж серый — для активации нужна подписка или LTE."
      />
      {payload.servers.length === 0 ? (
        <div className="rounded-2xl border border-border/60 bg-card/40 p-8 text-center text-sm text-muted-foreground">
          Не удалось загрузить список серверов. Возможно, профиль ещё создаётся в Remnawave.
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {payload.servers.map((server) => (
            <ServerCard key={server.uuid || server.name} server={server} />
          ))}
        </div>
      )}
    </div>
  );
}

function ServerCard({ server }: { server: Server }) {
  return (
    <Card className={server.available ? "" : "opacity-70"}>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Globe className="h-4 w-4 text-primary" />
            {server.display_name || server.name}
          </CardTitle>
          <KindBadge kind={server.kind} />
        </div>
        <CardDescription className="font-mono text-[11px]">{server.name}</CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{server.members ? `Активных: ${server.members}` : "—"}</span>
        {server.is_active ? (
          <Badge variant="success">Подключено</Badge>
        ) : server.available ? (
          <Badge variant="info">Доступно</Badge>
        ) : (
          <Badge variant="muted">Купите подписку</Badge>
        )}
      </CardContent>
    </Card>
  );
}

function KindBadge({ kind }: { kind: Server["kind"] }) {
  switch (kind) {
    case "free":
      return <Badge variant="success">FREE</Badge>;
    case "lte":
      return <Badge variant="warn">LTE</Badge>;
    case "paid":
      return <Badge variant="default">PAID</Badge>;
    default:
      return <Badge variant="muted">EXTRA</Badge>;
  }
}
