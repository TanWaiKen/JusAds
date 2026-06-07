import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export default function AboutUs() {
  const containerRef = useRef<HTMLElement>(null);

  useGSAP(() => {
    gsap.fromTo(".ad-compare-card",
      { y: 40, autoAlpha: 0 },
      {
        y: 0,
        autoAlpha: 1,
        stagger: 0.15,
        duration: 0.8,
        ease: "back.out(1.2)",
        scrollTrigger: {
          trigger: "#about",
          start: "top 75%",
        }
      }
    );
  }, { scope: containerRef });

  return (
    <section ref={containerRef} id="about" className="max-w-max-content-width mx-auto px-6 md:px-10 mt-[120px] mb-[80px]">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16 items-center text-left">
        <div className="flex flex-col">
          <h2 className="font-bold tracking-tight text-foreground mb-6 leading-[1.1]">
            Built for the <br />
            <span className="text-blue-600 dark:text-blue-400">nuances of SEA.</span>
          </h2>
          <p className="text-body-md md:text-body-lg text-text-body leading-relaxed mb-4">
            Global tools don't understand the complex cultural tapestry of Southeast Asia. A direct translation often misses the mark—or causes brand damage.
          </p>
          <p className="text-body-md md:text-body-lg text-text-body leading-relaxed">
            JusAds empowers brands to scale seamlessly. We combine generative AI with deep, localized cultural models to ensure your message is not just heard, but felt.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          {/* Original */}
          <div className="ad-compare-card bg-surface-card rounded-xl p-4 border border-border-default shadow-sm flex flex-col transition-all duration-300 hover:-translate-y-1 hover:shadow-md">
            <div className="flex justify-between items-start mb-3">
              <div>
                <h3 className="text-sm font-bold text-foreground">Original Poster</h3>
                <p className="text-[10px] text-text-caption mt-1">Your uploaded ad</p>
              </div>
              <span className="bg-surface-inset text-text-caption px-2 py-1 rounded-full text-[10px] font-semibold">Original</span>
            </div>
            <div className="flex-1 bg-white rounded-lg overflow-hidden shadow-[0_0_0_1px_rgba(0,0,0,0.08)] flex flex-col aspect-4/5">
              <div className="bg-black text-white p-2 flex justify-between items-center shrink-0">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full bg-white flex items-center justify-center text-black font-bold text-[10px]">S</div>
                  <div className="flex flex-col">
                    <span className="text-[10px] font-bold leading-none">sanfewomxn</span>
                    <span className="text-[8px] text-gray-300 mt-0.5">Sponsored</span>
                  </div>
                </div>
                <span className="bg-gray-800 text-white text-[8px] font-bold px-1.5 py-[2px] rounded-full">US Western</span>
              </div>
              <img src="/original_ad.png" alt="Original Ad" className="w-full flex-1 object-cover min-h-0" />
              <div className="bg-white p-3 text-xs border-t border-gray-100 text-gray-800">
                <span className="font-bold mr-1">sanfewomxn</span>Hey, try our new serum!
              </div>
            </div>
          </div>

          {/* Adapted */}
          <div className="ad-compare-card bg-surface-card rounded-xl p-4 border border-[#0a72ef]/30 shadow-[0_8px_30px_rgba(10,114,239,0.1)] flex flex-col transition-all duration-300 hover:-translate-y-1 hover:shadow-lg">
            <div className="flex justify-between items-start mb-3">
              <div>
                <h3 className="text-sm font-bold text-[#0a72ef]">Adapted Poster</h3>
                <p className="text-[10px] text-text-caption mt-1">MY Culture optimized</p>
              </div>
              <span className="bg-[#0a72ef] text-white px-2 py-1 rounded-full text-[10px] font-semibold">New</span>
            </div>
            <div className="flex-1 bg-white rounded-lg overflow-hidden shadow-[0_0_0_1px_rgba(10,114,239,0.2)] flex flex-col aspect-4/5">
              <div className="bg-black text-white p-2 flex justify-between items-center shrink-0">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full bg-white flex items-center justify-center text-black font-bold text-[10px]">S</div>
                  <div className="flex flex-col">
                    <span className="text-[10px] font-bold leading-none">sanfewomxn</span>
                    <span className="text-[8px] text-gray-300 mt-0.5">Sponsored</span>
                  </div>
                </div>
                <span className="bg-[#0a72ef] text-white text-[8px] font-bold px-1.5 py-[2px] rounded-full">MY Malaysian</span>
              </div>
              <img src="/adapted_ad.png" alt="Adapted Ad" className="w-full flex-1 object-cover min-h-0" />
              <div className="bg-white p-3 text-xs border-t border-[#0a72ef]/10 text-gray-800">
                <span className="font-bold mr-1 text-[#0a72ef]">sanfewomxn</span>Jom cuba serum baru!
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
