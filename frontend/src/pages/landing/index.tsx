import { useState, useRef } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import FloatingButton from "@/components/floating-button";
import { LoginModal } from "@/components/login-modal";
import Header, { type AuthAction } from "./Header";
import Hero from "./Hero";
import AboutUs from "./AboutUs";
import Features from "./Features";
import Pricing from "./Pricing";
import Faq from "./Faq";
import Footer from "./Footer";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export default function LandingPage() {
  const { isAuthenticated, status } = useAuth();
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const onAuthAction: AuthAction = {
    isAuthenticated,
    onOpenLogin: () => setIsLoginOpen(true),
    status,
  };

  useGSAP(() => {
    gsap.fromTo("header", { y: -20, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.7, ease: "power3.out" });
  }, { scope: containerRef });

  return (
    <div ref={containerRef} className="relative min-h-dvh bg-background transition-colors duration-500 font-sans flex flex-col">
      {/* Paper Grain Texture Layer — full landing page background */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none z-30 opacity-[0.06] mix-blend-overlay" xmlns="http://www.w3.org/2000/svg">
        <filter id="paperEmboss">
          <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="3" result="noise" />
          <feDiffuseLighting in="noise" lightingColor="#ffffff" surfaceScale="2">
            <feDistantLight azimuth="45" elevation="60" />
          </feDiffuseLighting>
          <feBlend mode="multiply" in="SourceGraphic" in2="noise" />
        </filter>
        <rect width="100%" height="100%" filter="url(#paperEmboss)" />
      </svg>

      <div className="relative z-10 flex flex-col flex-1">
        <Header onAuthAction={onAuthAction} />
        <Hero onAuthAction={onAuthAction} />
        <AboutUs />
        <Features />
        <Pricing onAuthAction={onAuthAction} />
        <Faq />
        <div className="mt-auto">
          <Footer />
        </div>
        <FloatingButton />
      </div>
      <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} />
    </div>
  );
}
