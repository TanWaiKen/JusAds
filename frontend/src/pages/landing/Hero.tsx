import { useRef } from "react";
import { ArrowRight } from "lucide-react";
import { useNavigate } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import type { AuthAction } from "./Header";

gsap.registerPlugin(useGSAP);

export default function Hero({ onAuthAction }: { onAuthAction: AuthAction }) {
  const containerRef = useRef<HTMLElement>(null);
  const navigate = useNavigate();
  const isLoading = onAuthAction.status === "loading";

  function handleStartDeploying() {
    if (onAuthAction.isAuthenticated) navigate("/dashboard");
    else onAuthAction.onOpenLogin();
  }

  useGSAP(() => {
    const tl = gsap.timeline({ defaults: { ease: "power3.out", duration: 0.6 } });

    tl.fromTo(".hero-title", { y: 30, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.8 });
    tl.fromTo(".hero-underline", { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: "power2.out", transformOrigin: "left center" }, "-=0.2");
    tl.fromTo(".hero-subheading", { y: 20, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.5 }, "-=0.4");
    tl.fromTo(".hero-desc", { y: 20, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.6 }, "-=0.3");
    tl.fromTo(".hero-ctas", { y: 20, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.5 }, "-=0.4");

    // Neon glow entrance
    tl.fromTo(".neon-glow",
      { autoAlpha: 0 },
      { autoAlpha: 1, duration: 0.4, ease: "power2.out" },
      "-=0.6"
    );

    // Draw neon curve paths from left to right
    const neonPaths = containerRef.current?.querySelectorAll(".neon-path");
    neonPaths?.forEach((path) => {
      const length = (path as SVGPathElement).getTotalLength();
      gsap.set(path, { strokeDasharray: length, strokeDashoffset: length });
      tl.to(path, { strokeDashoffset: 0, duration: 1.8, ease: "power2.inOut" }, "-=1.6");
    });

    // Draw the fill path
    const fillPath = containerRef.current?.querySelector(".neon-fill");
    if (fillPath) {
      gsap.set(fillPath, { autoAlpha: 0 });
      tl.to(fillPath, { autoAlpha: 1, duration: 1, ease: "power2.in" }, "-=1.2");
    }

    // Subtle continuous shimmer after draw completes
    gsap.to(".neon-glow svg", {
      x: 10,
      duration: 4,
      ease: "sine.inOut",
      yoyo: true,
      repeat: -1,
    });
  }, { scope: containerRef });

  return (
    <section ref={containerRef} className="relative flex flex-col items-center text-center px-6 lg:px-12 pt-[160px] pb-[120px] min-h-screen justify-center overflow-visible">

      <div className="max-w-[800px] flex flex-col items-center z-10">

        <h1 className="hero-title font-semibold text-text-heading mb-0 tracking-[-0.02em] leading-[1.1]">
          Launch{" "}
          <span className="relative inline-block">
            <span className="text-text-heading">AI Ads.</span>
            {/* Hand-drawn SVG underline */}
            <svg className="hero-underline absolute -bottom-2 left-0 w-full" viewBox="0 0 200 12" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
              <path d="M2 8.5C30 3 60 2 100 5.5C140 9 170 7.5 198 4" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="text-text-heading" />
            </svg>
          </span>
          <br />
          In Minutes.
        </h1>

        <p className="hero-subheading text-headline-sm md:text-[28px] font-medium text-text-heading mt-gutter mb-margin-page leading-[1.4]">
          Built for Southeast Asia's nuances.
        </p>

        <p className="hero-desc text-[22px] text-text-body max-w-[600px] leading-[1.6] font-normal">
          Create scroll-stopping, culturally tuned campaigns for SEA instantly. No editing skills required.
        </p>

        <div className="hero-ctas flex flex-col sm:flex-row items-center gap-3 mt-[30px]">
          <button
            onClick={handleStartDeploying}
            disabled={isLoading}
            className="inline-flex items-center bg-black hover:bg-neutral-900 active:scale-[0.98] text-white border-[1.5px] border-black dark:bg-white dark:text-black dark:border-white dark:hover:bg-gray-100 px-4 md:px-5 py-3 rounded-[6px] text-xs font-bold uppercase tracking-wider transition-premium brutalist-shadow-subtle dark:shadow-none disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            Start Deploying
          </button>
          <a href="#how-it-works">
            <button className="inline-flex items-center gap-2 bg-white hover:bg-[#f6f6f5] active:scale-[0.98] text-black border-[1.5px] border-black dark:border-white dark:bg-white/10 dark:text-white dark:hover:bg-white/15 px-4 md:px-5 py-3 rounded-[6px] text-xs font-bold uppercase tracking-wider transition-premium brutalist-shadow-black dark:shadow-none cursor-pointer">
              View Templates <ArrowRight className="w-4 h-4" />
            </button>
          </a>
        </div>
      </div>

      {/* Neon gradient SVG — clipped container at bottom of hero (Relume-style) */}
      <div className="neon-glow absolute bottom-0 left-0 w-full h-[50%] pointer-events-none z-0 overflow-hidden">
        <svg viewBox="0 0 1000 500" preserveAspectRatio="none" className="absolute bottom-[-10%] left-[-10%] w-[120%] h-[120%]" style={{ filter: "blur(40px)" }}>
          <defs>
            <linearGradient id="heroNeonGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#ff7043" />
              <stop offset="40%" stopColor="#ff7043" />
              <stop offset="70%" stopColor="#a06ef3" />
              <stop offset="100%" stopColor="#a06ef3" />
            </linearGradient>
          </defs>
          {/* Base fill anchoring the bottom */}
          <path className="neon-fill" d="M-100,100 Q500,700 1100,100 L1100,700 L-100,700 Z" fill="url(#heroNeonGrad)" opacity="0.3" />
          {/* Outer dispersion — color decays outward */}
          <path className="neon-path" d="M-100,100 Q500,700 1100,100" fill="none" stroke="url(#heroNeonGrad)" strokeWidth="200" opacity="0.4" />
          {/* Core focal line — maximum clarity and intensity */}
          <path className="neon-path" d="M-100,100 Q500,700 1100,100" fill="none" stroke="url(#heroNeonGrad)" strokeWidth="60" opacity="0.85" />
        </svg>
      </div>

    </section>
  );
}
