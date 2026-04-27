"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { api, type ApiError, type PaymentResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

type Props = {
  endpoint: string;
  body: Record<string, unknown>;
  label: string;
  onSuccess?: (payment: PaymentResponse) => void;
  size?: "default" | "sm" | "lg" | "xl" | "icon";
  variant?: "default" | "gradient" | "secondary" | "outline" | "ghost" | "destructive" | "link";
  className?: string;
  disabled?: boolean;
};

export function PaymentLauncher({
  endpoint,
  body,
  label,
  onSuccess,
  size = "lg",
  variant = "gradient",
  className,
  disabled,
}: Props) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const launch = async () => {
    setLoading(true);
    setError(null);
    try {
      const returnUrl =
        typeof window !== "undefined" ? `${window.location.origin}/cabinet/payment-callback` : undefined;
      const payload: Record<string, unknown> = { ...body };
      if (returnUrl) payload.return_url = returnUrl;
      const data = await api.post<PaymentResponse>(endpoint, payload);
      if (typeof window !== "undefined") {
        sessionStorage.setItem(
          "kaira:last_payment",
          JSON.stringify({ payment_id: data.payment_id, kind: data.kind, ts: Date.now() }),
        );
      }
      onSuccess?.(data);
      if (data.confirmation_url) {
        window.location.href = data.confirmation_url;
      }
    } catch (err) {
      setError((err as ApiError).detail || "Не удалось создать платёж");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <Button
        type="button"
        size={size}
        variant={variant}
        className={cn(buttonVariants({ variant, size }), className)}
        onClick={launch}
        disabled={disabled || loading}
      >
        {loading && <Loader2 className="h-4 w-4 animate-spin" />}
        {label}
      </Button>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
