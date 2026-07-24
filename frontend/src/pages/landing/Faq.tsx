import { useState, useRef } from "react";
import { ChevronDown } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

// ─── Static Data ──────────────────────────────────────────────────────────────

const FAQS = [
  { question: "What languages and dialects can I use?", answer: "JusAds currently supports Bahasa Melayu, Manglish, Tamil, local Mandarin, and Singlish for Malaysian and Singaporean customers. Indonesian and Thai support is planned." },
  { question: "Will JusAds publish an ad without asking me?", answer: "No. You review and approve every result before it is downloaded or published. JusAds also checks for sensitive or controversial content." },
  { question: "Do I need design or marketing skills?", answer: "No. Upload a product photo or an existing ad, choose the customers you want to reach, and follow the guided steps. Advanced options are available when you need them." },
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
        <p className="text-3xl md:text-4xl font-semibold tracking-tight text-foreground mb-4 leading-tight">Frequently asked questions</p>
        <p className="text-body-lg text-text-body">Clear answers before you create your first ad.</p>
      </div>
      <div className="space-y-4">
        {FAQS.map((faq, i) => (
          <div key={i} className="faq-item bg-surface-card border border-border-default rounded-xl overflow-hidden shadow-sm">
            <button className="w-full px-6 py-5 flex items-center justify-between text-left focus-visible:outline-2 focus-visible:outline-offset-[-3px] focus-visible:outline-blue-600" onClick={() => setOpenIndex(openIndex === i ? null : i)} aria-expanded={openIndex === i} aria-controls={`faq-answer-${i}`}>
              <span className="text-body-md font-medium text-foreground">{faq.question}</span>
              <ChevronDown className={`w-5 h-5 text-text-caption transition-transform duration-300 ${openIndex === i ? "rotate-180" : ""}`} />
            </button>
            <div id={`faq-answer-${i}`} className={`px-6 overflow-hidden transition-all duration-300 ease-in-out ${openIndex === i ? "max-h-96 pb-5 opacity-100" : "max-h-0 opacity-0"}`}>
              <p className="text-[15px] text-text-body leading-relaxed">{faq.answer}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
