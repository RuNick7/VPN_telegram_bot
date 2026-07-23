import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { api, type Me } from "./api";

export async function getServerCookieHeader(): Promise<string> {
  const jar = await cookies();
  return jar
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");
}

export async function getMe(): Promise<Me | null> {
  const cookieHeader = await getServerCookieHeader();
  if (!cookieHeader) return null;
  try {
    return await api.get<Me>("/api/me", { cookieHeader });
  } catch {
    return null;
  }
}

export async function requireAuth(): Promise<Me> {
  const me = await getMe();
  if (!me) {
    redirect("/auth/signin");
  }
  return me;
}

export async function redirectIfAuthed(target = "/cabinet"): Promise<void> {
  const me = await getMe();
  if (me) redirect(target);
}
