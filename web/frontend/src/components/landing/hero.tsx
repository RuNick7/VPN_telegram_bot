"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";

export function Hero() {
  return (
    <section className="aurora-bg relative overflow-hidden">
      <div className="relative mx-auto flex w-full max-w-6xl flex-col items-center gap-10 px-4 py-20 text-center md:py-28 md:px-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-card/40 px-4 py-1.5 text-xs text-muted-foreground backdrop-blur"
        >
          <ShieldCheck className="h-3.5 w-3.5 text-primary" />
          Без логов · без паролей · через Telegram
        </motion.div>
        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: "easeOut", delay: 0.05 }}
          className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl md:text-6xl"
        >
          Быстрый VPN <span className="gradient-text">для повседневной</span> жизни
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: "easeOut", delay: 0.15 }}
          className="max-w-2xl text-balance text-base text-muted-foreground sm:text-lg"
        >
          Современные протоколы, серверы по всему миру и LTE-режим, чтобы стримить и работать
          без задержек. Регистрация по email и привязка Telegram — никаких паролей.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: "easeOut", delay: 0.25 }}
          className="flex flex-col items-center gap-3 sm:flex-row"
        >
          <Button asChild size="xl" variant="gradient" className="w-full sm:w-auto">
            <Link href="/auth/signup">
              Попробовать бесплатно
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button asChild size="xl" variant="outline" className="w-full sm:w-auto">
            <Link href="/#features">
              Что внутри
              <Zap className="h-4 w-4" />
            </Link>
          </Button>
        </motion.div>
      </div>
    </section>
  );
}
