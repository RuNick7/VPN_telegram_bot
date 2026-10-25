/*
 * Web Push from the browser's side: what this browser can do, and keeping its
 * subscription registered with the site.
 *
 * Shared by the profile, which has the controls, and pwa.js, which re-sends
 * an existing subscription once per visit to the cabinet. The re-send is what
 * keeps a browser attached to the right account after a sign-in elsewhere or
 * an account merge, and what repairs a subscription the site's key changed
 * under.
 */

import { api } from "./core.js";

/** "ok" | "ios-install" (iPhone, not installed) | "unsupported". */
export function pushSupport(win = window) {
  const nav = win.navigator;
  const has = "serviceWorker" in nav && "PushManager" in win && "Notification" in win;
  if (has) return "ok";
  const ios = /iphone|ipad|ipod/i.test(nav.userAgent) || (nav.platform === "MacIntel" && nav.maxTouchPoints > 1);
  // Safari exposes push only inside an app added to the home screen.
  return ios ? "ios-install" : "unsupported";
}

/** The key the server signs with, as PushManager wants it. */
export function keyBytes(base64url) {
  const base64 = base64url.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}

function sameKey(subscription, key) {
  const current = subscription.options?.applicationServerKey;
  if (!current) return true; // older browsers do not say; assume it matches
  const a = new Uint8Array(current);
  return a.length === key.length && a.every((byte, i) => byte === key[i]);
}

export async function currentSubscription() {
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

async function register(subscription) {
  const { endpoint, keys } = subscription.toJSON();
  await api("/api/push/subscription", {
    method: "PUT",
    body: { endpoint, p256dh: keys.p256dh, auth: keys.auth },
  });
}

/** Asks for permission if needed, subscribes, and registers with the site. */
export async function subscribe(publicKey) {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission;
  const key = keyBytes(publicKey);
  const registration = await navigator.serviceWorker.ready;
  let subscription = await registration.pushManager.getSubscription();
  if (subscription && !sameKey(subscription, key)) {
    await subscription.unsubscribe();
    subscription = null;
  }
  subscription ??= await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
  await register(subscription);
  return "granted";
}

export async function unsubscribe() {
  const subscription = await currentSubscription();
  if (!subscription) return;
  const { endpoint } = subscription.toJSON();
  await subscription.unsubscribe();
  await api("/api/push/subscription", { method: "DELETE", body: { endpoint } });
}

/** Re-registers an existing subscription, quietly. Never prompts. */
export async function syncSubscription() {
  if (pushSupport() !== "ok" || Notification.permission !== "granted") return;
  const status = await api("/api/push");
  if (!status.push_enabled) return;
  const subscription = await currentSubscription();
  if (!subscription) return;
  if (!sameKey(subscription, keyBytes(status.public_key))) {
    await subscribe(status.public_key);
    return;
  }
  await register(subscription);
}
