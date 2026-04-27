export type ApiError = {
  status: number;
  detail: string;
  raw?: unknown;
};

const browserDefaults: RequestInit = {
  credentials: "include",
  headers: { "Content-Type": "application/json", "X-Requested-With": "fetch" },
};

function isServer(): boolean {
  return typeof window === "undefined";
}

function backendBase(): string {
  if (isServer()) {
    return process.env.API_BASE_URL || "http://127.0.0.1:8000";
  }
  return "";
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { cookieHeader?: string } = {},
): Promise<T> {
  const base = backendBase();
  const url = path.startsWith("http") ? path : `${base}${path}`;
  const { cookieHeader, ...rest } = init;

  const headers: HeadersInit = {
    ...browserDefaults.headers,
    ...(rest.headers || {}),
  };
  if (cookieHeader) {
    (headers as Record<string, string>)["Cookie"] = cookieHeader;
  }

  const response = await fetch(url, {
    ...browserDefaults,
    ...rest,
    headers,
    cache: rest.cache ?? "no-store",
  });

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    const detail =
      (data && typeof data === "object" && "detail" in data && typeof (data as { detail: unknown }).detail === "string"
        ? ((data as { detail: string }).detail)
        : `Ошибка ${response.status}`);
    const error: ApiError = { status: response.status, detail, raw: data };
    throw error;
  }

  return data as T;
}

export const api = {
  get: <T>(path: string, init?: RequestInit & { cookieHeader?: string }) =>
    apiFetch<T>(path, { ...init, method: "GET" }),
  post: <T>(path: string, body?: unknown, init?: RequestInit & { cookieHeader?: string }) =>
    apiFetch<T>(path, {
      ...init,
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
};

export type SubscriptionSnapshot = {
  telegram_id: number;
  subscription_ends: number;
  expire_at: number;
  is_active: boolean;
  subscription_url: string;
  panel_user_exists: boolean;
  expires_iso: string;
  days_left: number;
  qr_data_url?: string | null;
};

export type ReferralSummary = {
  referrer_tag: string | null;
  referred_people: number;
  gifted_subscriptions: number;
  tier: number;
};

export type Me = {
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  photo_url: string | null;
  email: string | null;
  is_telegram_linked: boolean;
  subscription: SubscriptionSnapshot | null;
  lte_remaining_bytes: number;
  lte_remaining_gb: number;
  referrals: ReferralSummary;
};

export type Tariff = {
  months: number;
  days: number;
  price: number;
  monthly_equivalent: number;
  full_price: number;
  discount_percent: number;
};

export type TariffsResponse = {
  referred_people: number;
  tariffs: Tariff[];
};

export type LtePackage = { gb: number; price: number };
export type LtePackagesResponse = { packages: LtePackage[] };
export type GiftTariff = { months: number; price: number; days: number };
export type GiftTariffsResponse = { tariffs: GiftTariff[] };

export type Server = {
  uuid: string;
  name: string;
  display_name: string;
  kind: "paid" | "lte" | "free" | "other";
  members: number;
  available: boolean;
  is_active: boolean;
};

export type ServersResponse = { servers: Server[] };

export type ReferralOverview = {
  telegram_tag?: string | null;
  referrer_tag?: string | null;
  referred_people: number;
  bonus_threshold?: number;
  bonus_received?: boolean;
  gifted_subscriptions?: number;
  share_link?: string | null;
};

export type PaymentResponse = {
  payment_id: string;
  status: string;
  confirmation_url: string;
  amount: number;
  currency: "RUB";
  kind: "subscription" | "lte_gb" | "gift";
  months?: number;
  days_to_extend?: number;
  lte_gb?: number;
};

export type PaymentSnapshot = {
  payment_id: string;
  status: string;
  local_status: string;
  metadata: Record<string, unknown>;
  confirmation_url: string | null;
};

export type TelegramLinkStart = {
  token: string;
  deeplink: string;
  expires_at: number;
  bot_username?: string | null;
};

export type TelegramLinkStatus = {
  status: "pending" | "confirmed" | "expired";
  telegram_id: number | null;
  username: string | null;
};

export type InstructionStep = {
  title: string;
  description?: string;
};

export type InstructionApp = {
  name: string;
  store_url?: string;
  store_url_ru?: string;
  apk_url?: string;
  download_url?: string;
  deb_url?: string;
};

export type Instruction = {
  platform: string;
  subscription_url: string;
  deeplink: string | null;
  auto_link: string | null;
  title: string;
  app: InstructionApp;
  steps: InstructionStep[];
  qr_data_url: string | null;
  subscription: SubscriptionSnapshot;
};
