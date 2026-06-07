import { useState, useRef } from "react";
import { ChevronDown } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

// ─── Static Data ──────────────────────────────────────────────────────────────

const FAQS = [
  { question: "What languages and dialects do you currently support?", answer: "We currently offer deep localization models for Malaysian (Bahasa Melayu, Manglish, Tamil, local Mandarin dialects) and Singaporean (Singlish, local Mandarin) markets. We are actively expanding to Indonesia and Thailand." },
  { question: "How does JusAds ensure brand safety?", answer: "Our Trend Intelligence engine specifically filters out sensitive, political, or controversial local trends. Before any asset is exported, it passes through our automated cultural resonance check to ensure strict brand safety." },
  { question: "Do I need technical skills to use the platform?", answer: "Not at all. JusAds is designed for marketing teams. You simply upload your base English assets, select your target demographic, and our AI pipeline handles the transcreation, visual masking, and rendering automatically." },
] as const;

// ─── FAQ Component ────────────────────────────────────────────────────────────

export default function Faq() {
  const containerRef = useRef<HTMLElement>(null);
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  useGSAP(() => {
    gsap.fromTo(".faq-item",
      { y: 20, autoAlpha: 0 },
      {
        y: 0,
        autoAlpha: 1,
        stagger: 0.1,
        duration: 0.6,
        ease: "power3.out",
        scrollTrigger: {
          trigger: "#faq",
          start: "top 80%",
        }
      }
    );
  }, { scope: containerRef });

  return (
    <section ref={containerRef} id="faq" className="max-w-[800px] mx-auto px-6 lg:px-12 mt-[120px] mb-[160px]">
      <div className="text-center mb-12">
        <h2 className="font-semibold tracking-tight text-foreground mb-4 leading-tight">Frequently asked questions</h2>
        <p className="text-body-lg text-text-body">Everything you need to know about scaling your localization.</p>
      </div>
      <div className="space-y-4">
        {FAQS.map((faq, i) => (
          <div key={i} className="faq-item bg-surface-card border border-border-default rounded-xl overflow-hidden shadow-sm">
            <button className="w-full px-6 py-5 flex items-center justify-between text-left focus:outline-none" onClick={() => setOpenIndex(openIndex === i ? null : i)}>
              <span className="text-body-md font-medium text-foreground">{faq.question}</span>
              <ChevronDown className={`w-5 h-5 text-text-caption transition-transform duration-300 ${openIndex === i ? "rotate-180" : ""}`} />
            </button>
            <div className={`px-6 overflow-hidden transition-all duration-300 ease-in-out ${openIndex === i ? "max-h-96 pb-5 opacity-100" : "max-h-0 opacity-0"}`}>
              <p className="text-[15px] text-text-body leading-relaxed">{faq.answer}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
