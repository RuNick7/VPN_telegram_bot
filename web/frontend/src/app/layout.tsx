import type { Metadata, Viewport } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";

import { ServiceWorkerRegistrar } from "@/components/common/service-worker-registrar";
import { ThemeProvider } from "@/components/common/theme-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "KairaVPN — быстрый и безопасный VPN",
    template: "%s · KairaVPN",
  },
  description:
    "KairaVPN — VPN с современными протоколами, мгновенным подключением и приятным интерфейсом. Без логов и без паролей.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://app.kairavpn.pro"),
  applicationName: "KairaVPN",
  manifest: "/manifest.webmanifest",
  openGraph: {
    title: "KairaVPN",
    description: "Быстрый и безопасный VPN с поддержкой Telegram-входа.",
    type: "website",
    siteName: "KairaVPN",
  },
  appleWebApp: {
    capable: true,
    title: "Kaira",
    statusBarStyle: "black-translucent",
  },
  icons: {
    icon: [
      { url: "/favicon.ico" },
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  formatDetection: { telephone: false, email: false, address: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#0b0b13" },
    { media: "(prefers-color-scheme: dark)", color: "#0b0b13" },
  ],
  initialScale: 1,
  width: "device-width",
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" suppressHydrationWarning className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-screen overflow-x-hidden font-sans">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
          {children}
        </ThemeProvider>
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}
