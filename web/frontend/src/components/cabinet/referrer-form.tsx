"use client";

import * as React from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type ApiError } from "@/lib/api";

export function ReferrerForm({ existingTag }: { existingTag: string | null }) {
  const [tag, setTag] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [success, setSuccess] = React.useState<string | null>(null);
  const [storedTag, setStoredTag] = React.useState(existingTag);

  if (storedTag) {
    return (
      <div className="rounded-xl bg-muted/40 px-4 py-3 text-sm">
        Пригласивший указан: <span className="font-mono text-foreground">@{storedTag}</span>
      </div>
    );
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const data = await api.post<{ ok: true; referrer_tag: string; message: string }>(
        "/api/referrals/set",
        { referrer_tag: tag.trim().replace(/^@/, "") },
      );
      setStoredTag(data.referrer_tag);
      setSuccess(data.message || "Пригласивший указан.");
    } catch (err) {
      setError((err as ApiError).detail || "Не удалось указать пригласившего.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Label htmlFor="referrer">Кто вас пригласил?</Label>
      <Input
        id="referrer"
        placeholder="@username"
        value={tag}
        onChange={(event) => setTag(event.target.value)}
        disabled={submitting}
      />
      {error && <p className="text-sm text-destructive">{error}</p>}
      {success && (
        <div className="flex items-center gap-2 text-sm text-emerald-300">
          <CheckCircle2 className="h-4 w-4" />
          {success}
        </div>
      )}
      <Button type="submit" size="lg" variant="gradient" disabled={submitting || !tag.trim()}>
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        Указать пригласившего
      </Button>
    </form>
  );
}
