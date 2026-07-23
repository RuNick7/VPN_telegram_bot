"use client";

import * as React from "react";
import { Check, Copy, Smartphone } from "lucide-react";

import { Button } from "@/components/ui/button";
import { detectPlatform } from "@/lib/utils";

export function ConnectButton({ subscriptionUrl }: { subscriptionUrl: string }) {
  const [platform, setPlatform] = React.useState<ReturnType<typeof detectPlatform>>("unknown");
  const [copied, setCopied] = React.useState(false);

  React.useEffect(() => {
    setPlatform(detectPlatform());
  }, []);

  const happLink = subscriptionUrl
    ? `happ://add/${subscriptionUrl.replace(/^https?:\/\//, "")}`
    : "";

  const onCopy = async () => {
    if (!subscriptionUrl) return;
    try {
      await navigator.clipboard.writeText(subscriptionUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  if (!subscriptionUrl) {
    return (
      <Button size="lg" disabled>
        <Smartphone className="h-4 w-4" />
        Подключение готовится…
      </Button>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button asChild size="lg" variant="gradient">
        <a href={happLink} target="_blank" rel="noopener noreferrer">
          <Smartphone className="h-4 w-4" />
          Подключить ({platformLabel(platform)})
        </a>
      </Button>
      <Button size="lg" variant="outline" onClick={onCopy}>
        {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
        {copied ? "Скопировано" : "Копировать ссылку"}
      </Button>
    </div>
  );
}

function platformLabel(platform: ReturnType<typeof detectPlatform>): string {
  switch (platform) {
    case "ios":
      return "iOS";
    case "android":
      return "Android";
    case "macos":
      return "macOS";
    case "windows":
      return "Windows";
    case "linux":
      return "Linux";
    default:
      return "Happ";
  }
}
