import { Link } from "react-router";

// ─── Static Data ──────────────────────────────────────────────────────────────

const PRODUCT_LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#pricing", label: "Pricing" },
  { href: "#faq", label: "FAQ" },
] as const;

const COMPANY_LINKS = [
  { href: "#sample-result", label: "Sample result" },
  { href: "https://www.linkedin.com/company/95728322", label: "LinkedIn", external: true },
  { href: "mailto:hello@jusads.com", label: "Contact" },
] as const;

// ─── Footer Component ─────────────────────────────────────────────────────────

export default function Footer() {
  return (
    <footer className="w-full border-t border-border-default bg-background/50 backdrop-blur-md">
      <div className="w-full px-6 md:px-12 py-12">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-8">
          <div className="flex flex-col gap-4">
            <Link to="/" className="flex items-center gap-2">
              <img src="/logo-black.png" alt="JusAds Logo" className="h-8 w-auto block dark:hidden" />
              <img src="/logo-white.png" alt="JusAds Logo" className="h-8 w-auto hidden dark:block" />
              <span className="font-semibold text-body-md tracking-tight text-foreground">JusAds</span>
            </Link>
            <p className="text-label-ui text-text-caption">© {new Date().getFullYear()} JusAds. Local ads made simple.</p>
          </div>
          <div className="flex gap-8">
            <div className="flex flex-col gap-3">
              <p className="text-label-ui font-semibold text-foreground">Product</p>
              {PRODUCT_LINKS.map(({ href, label }) => (
                <a key={href} href={href} className="text-label-ui text-text-caption hover:text-foreground transition-colors">{label}</a>
              ))}
            </div>
            <div className="flex flex-col gap-3">
              <p className="text-label-ui font-semibold text-foreground">Company</p>
              {COMPANY_LINKS.map(({ href, label, ...rest }) => (
                <a
                  key={href}
                  href={href}
                  {...("external" in rest ? { target: "_blank", rel: "noreferrer" } : {})}
                  className="text-label-ui text-text-caption hover:text-foreground transition-colors"
                >
                  {label}
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
