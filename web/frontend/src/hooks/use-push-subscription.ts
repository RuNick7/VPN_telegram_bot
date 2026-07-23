"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";

export type PushStatus =
  | "loading"
  | "unsupported"
  | "blocked"
  | "default"
  | "subscribed"
  | "unconfigured";

const SUPPORT_FLAGS_OK =
  typeof window !== "undefined" &&
  "serviceWorker" in navigator &&
  "PushManager" in window &&
  "Notification" in window;

function urlBase64ToUint8Array(base64String: string): ArrayBuffer {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const output = new ArrayBuffer(rawData.length);
  const view = new Uint8Array(output);
  for (let i = 0; i < rawData.length; i += 1) {
    view[i] = rawData.charCodeAt(i);
  }
  return output;
}

async function getRegistration(): Promise<ServiceWorkerRegistration | null> {
  if (!SUPPORT_FLAGS_OK) return null;
  try {
    return (await navigator.serviceWorker.getRegistration("/")) || null;
  } catch {
    return null;
  }
}

export function usePushSubscription() {
  const [status, setStatus] = useState<PushStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!SUPPORT_FLAGS_OK) {
      setStatus("unsupported");
      return;
    }
    if (Notification.permission === "denied") {
      setStatus("blocked");
      return;
    }

    const reg = await getRegistration();
    if (!reg) {
      setStatus(Notification.permission === "granted" ? "default" : "default");
      return;
    }
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      setStatus("subscribed");
    } else if (Notification.permission === "granted") {
      setStatus("default");
    } else {
      setStatus("default");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const subscribe = useCallback(async () => {
    if (!SUPPORT_FLAGS_OK) return;
    setBusy(true);
    setError(null);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setStatus(permission === "denied" ? "blocked" : "default");
        return;
      }

      const reg = await navigator.serviceWorker.ready;

      let key: { public_key: string };
      try {
        key = await api.get<{ public_key: string }>("/api/push/vapid-public-key");
      } catch (err) {
        const status = (err as { status?: number })?.status;
        if (status === 503) {
          setStatus("unconfigured");
          setError("Push-уведомления ещё не настроены на сервере.");
          return;
        }
        throw err;
      }

      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key.public_key),
      });

      const json = sub.toJSON();
      await api.post("/api/push/subscribe", {
        endpoint: sub.endpoint,
        keys: json.keys,
      });
      setStatus("subscribed");
    } catch (err) {
      console.warn("[push] subscribe failed", err);
      setError("Не удалось включить уведомления. Попробуйте ещё раз.");
    } finally {
      setBusy(false);
    }
  }, []);

  const unsubscribe = useCallback(async () => {
    if (!SUPPORT_FLAGS_OK) return;
    setBusy(true);
    setError(null);
    try {
      const reg = await getRegistration();
      if (!reg) {
        setStatus("default");
        return;
      }
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        try {
          await api.post("/api/push/unsubscribe", { endpoint: sub.endpoint });
        } catch {
          // не страшно — всё равно отписываемся локально
        }
        await sub.unsubscribe();
      }
      setStatus("default");
    } finally {
      setBusy(false);
    }
  }, []);

  return { status, error, busy, subscribe, unsubscribe, refresh };
}
