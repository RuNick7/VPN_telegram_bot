import { NextResponse, type NextRequest } from "next/server";
import { cookies } from "next/headers";

import { api } from "@/lib/api";

async function handle(request: NextRequest) {
  const jar = await cookies();
  const cookieHeader = jar
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");
  try {
    await api.post("/api/auth/logout", undefined, { cookieHeader });
  } catch {
    // ignore
  }
  const target = new URL("/auth/signin", request.url);
  const response = NextResponse.redirect(target, { status: 303 });
  response.cookies.delete("kaira_session");
  return response;
}

export const POST = handle;
export const GET = handle;
