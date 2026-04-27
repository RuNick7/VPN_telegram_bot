"use client";

import { useEffect, useState } from "react";
import { Download, Share2, Smartphone, X } from "lucide-react";

import { Button } from "@/components/ui/button";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
};

const DISMISS_KEY = "kaira_install_dismissed_at";
const DISMISS_TTL_MS = 1000 * 60 * 60 * 24 * 7;

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  if (window.matchMedia?.("(display-mode: standalone)").matches) return true;
  return Boolean((navigator as Navigator & { standalone?: boolean }).standalone);
}

function isIos(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  if (/iPad|iPhone|iPod/.test(ua)) return true;
  return navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
}

function isDismissedRecently(): boolean {
  try {
    const ts = Number(localStorage.getItem(DISMISS_KEY));
    if (!ts) return false;
    return Date.now() - ts < DISMISS_TTL_MS;
  } catch {
    return false;
  }
}

function rememberDismiss() {
  try {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  } catch {
    // ignore
  }
}

export function InstallPrompt() {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [showIosHint, setShowIosHint] = useState(false);
  const [hidden, setHidden] = useState(true);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (isStandalone()) return;
    if (isDismissedRecently()) return;

    const handler = (event: Event) => {
      event.preventDefault();
      setInstallEvent(event as BeforeInstallPromptEvent);
      setHidden(false);
    };

    window.addEventListener("beforeinstallprompt", handler);

    if (isIos()) {
      setShowIosHint(true);
      setHidden(false);
    }

    return () => {
      window.removeEventListener("beforeinstallprompt", handler);
    };
  }, []);

  const handleInstall = async () => {
    if (!installEvent) return;
    try {
      await installEvent.prompt();
      const choice = await installEvent.userChoice;
      if (choice.outcome === "dismissed") rememberDismiss();
    } finally {
      setInstallEvent(null);
      setHidden(true);
    }
  };

  const dismiss = () => {
    rememberDismiss();
    setHidden(true);
  };

  if (hidden) return null;
  if (!installEvent && !showIosHint) return null;

  return (
    <div className="glass-strong relative flex flex-col gap-3 rounded-2xl px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
      <button
        type="button"
        onClick={dismiss}
        aria-label="Скрыть"
        className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <X className="h-4 w-4" />
      </button>
      <div className="flex items-start gap-3 pr-8">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/15 text-primary">
          <Smartphone className="h-5 w-5" />
        </div>
        <div>
          <div className="font-medium">Установить KairaVPN на главный экран</div>
          {installEvent ? (
            <p className="text-xs text-muted-foreground">
              Запускайте кабинет в один тап без браузера и панелей.
            </p>
          ) : (
            <p className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
              На iPhone нажмите{" "}
              <span className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-foreground">
                <Share2 className="h-3 w-3" /> Поделиться
              </span>
              {" "}и выберите{" "}
              <span className="rounded-md bg-muted px-1.5 py-0.5 text-foreground">
                На экран &laquo;Домой&raquo;
              </span>
              .
            </p>
          )}
        </div>
      </div>
      {installEvent ? (
        <Button onClick={handleInstall} className="self-end sm:self-auto">
          <Download className="mr-2 h-4 w-4" /> Установить
        </Button>
      ) : null}
    </div>
  );
}
