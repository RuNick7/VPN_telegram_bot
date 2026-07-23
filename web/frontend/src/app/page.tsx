import { SiteFooter } from "@/components/common/site-footer";
import { SiteHeader } from "@/components/common/site-header";
import { Faq } from "@/components/landing/faq";
import { Features } from "@/components/landing/features";
import { Hero } from "@/components/landing/hero";
import { PricingPreview } from "@/components/landing/pricing-preview";

export default function LandingPage() {
  return (
    <>
      <SiteHeader />
      <main className="relative">
        <Hero />
        <Features />
        <PricingPreview />
        <Faq />
      </main>
      <SiteFooter />
    </>
  );
}
