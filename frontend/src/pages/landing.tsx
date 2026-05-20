import { useState } from "react";
import { ArrowRight, PlayCircle, CheckCircle2, ChevronDown, Shield, Globe, Users } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/useAuth";
import FloatingButton from "@/components/floating-button";
import { LoginModal } from "@/components/login-modal";

// ─── Types ────────────────────────────────────────────────────────────────────

interface AuthAction {
  isAuthenticated: boolean;
  onOpenLogin: () => void;
  status: "loading" | "authenticated" | "unauthenticated";
}

// ─── Header ───────────────────────────────────────────────────────────────────

function Header({ onAuthAction }: { onAuthAction: AuthAction }) {
  const navigate = useNavigate();
  const { user, picture, logout } = useAuth();

  const { status, isAuthenticated } = onAuthAction;
  const name = user?.profile?.name ?? "";
  const initials = name ? name.slice(0, 2).toUpperCase() : "?";

  const handleAuthAction = () => {
    if (isAuthenticated) navigate("/dashboard");
    else onAuthAction.onOpenLogin();
  };

  return (
    <header className="absolute top-0 left-0 right-0 z-50 w-full animate-in slide-in-from-top-4 duration-700 ease-out">
      <nav className="flex items-center justify-between w-full px-6 py-4">
        <Link to="/" className="flex items-center gap-2 group">
          <img src="/logo-black.png" alt="JusAds Logo" className="h-8 w-auto block dark:hidden group-hover:scale-105 transition-transform duration-200" />
          <img src="/logo-white.png" alt="JusAds Logo" className="h-8 w-auto hidden dark:block group-hover:scale-105 transition-transform duration-200" />
          <span className="font-semibold text-[16px] tracking-tight text-foreground">JusAds</span>
        </Link>

        <div className="hidden md:flex items-center gap-8">
          <a href="#about"        className="text-[14px] font-medium text-gray-600 dark:text-gray-400 hover:text-foreground transition-colors duration-200">About Us</a>
          <a href="#how-it-works" className="text-[14px] font-medium text-gray-600 dark:text-gray-400 hover:text-foreground transition-colors duration-200">How it works</a>
          <a href="#features"     className="text-[14px] font-medium text-gray-600 dark:text-gray-400 hover:text-foreground transition-colors duration-200">Features</a>
          <a href="#pricing"      className="text-[14px] font-medium text-gray-600 dark:text-gray-400 hover:text-foreground transition-colors duration-200">Pricing</a>
          <a href="#faq"          className="text-[14px] font-medium text-gray-600 dark:text-gray-400 hover:text-foreground transition-colors duration-200">FAQ</a>
        </div>

        <div className="flex items-center gap-3">
          {status === "loading" && (
            <>
              <Skeleton className="h-[32px] w-[56px] rounded-[6px]" />
              <Skeleton className="h-[36px] w-[104px] rounded-[6px]" />
            </>
          )}
          {status === "unauthenticated" && (
            <>
              <button onClick={handleAuthAction} className="text-[14px] font-medium text-gray-600 dark:text-gray-400 hover:text-foreground px-2 py-1 transition-all">
                Log In
              </button>
              <button onClick={handleAuthAction} className="bg-foreground text-background text-[14px] font-medium px-[16px] py-[8px] rounded-[6px] hover:opacity-90 active:scale-95 transition-all">
                Try for free
              </button>
            </>
          )}
          {status === "authenticated" && user && (
            <div className="flex items-center gap-3">
              <button onClick={() => navigate("/dashboard")} className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                <div className="h-8 w-8 rounded-full overflow-hidden ring-2 ring-gray-200 dark:ring-white/20 shrink-0">
                  {picture
                    ? <img src={picture} alt="Profile" className="h-full w-full object-cover" referrerPolicy="no-referrer" />
                    : <div className="h-full w-full flex items-center justify-center bg-foreground text-background text-[12px] font-semibold">{initials}</div>
                  }
                </div>
                <span className="text-[14px] font-medium text-foreground hidden sm:block">{user.profile.name}</span>
              </button>
              <button onClick={() => void logout()} className="text-[14px] font-medium text-gray-500 dark:text-gray-400 hover:text-foreground px-2 py-1 transition-all">
                Log Out
              </button>
            </div>
          )}
        </div>
      </nav>
    </header>
  );
}

// ─── Hero ─────────────────────────────────────────────────────────────────────

function Hero({ onAuthAction }: { onAuthAction: AuthAction }) {
  const navigate = useNavigate();
  const isLoading = onAuthAction.status === "loading";

  function handleStartDeploying() {
    if (onAuthAction.isAuthenticated) navigate("/dashboard");
    else onAuthAction.onOpenLogin();
  }

  return (
    <section className="flex flex-col items-center text-center px-6 lg:px-12 py-[120px]">
      <div className="max-w-[800px] flex flex-col items-center z-10">
        <div className="inline-flex items-center gap-2 bg-[#ebf5ff] text-[#0068d6] rounded-full px-3 py-[2px] mb-10 shadow-sm">
          <span className="text-[12px] font-semibold uppercase tracking-widest">Update</span>
          <span className="text-[12px] font-medium">JusAds v1.0 is now live</span>
        </div>

        <h1 className="text-[48px] md:text-[64px] font-semibold text-foreground mb-8 max-w-[700px] tracking-[-2.6px] leading-none">
          Launch <span className="text-transparent bg-clip-text bg-linear-to-r from-[#0080FF] via-[#FF1493] to-[#00FFFF]">AI Ads.</span><br />
          In Minutes.
        </h1>

        <p className="text-[20px] text-gray-600 dark:text-gray-400 mb-10 max-w-[700px] leading-[1.80]">
          Create scroll-stopping, culturally tuned campaigns for SEA instantly. No editing skills required.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4 mb-[80px]">
          <button
            onClick={handleStartDeploying}
            disabled={isLoading}
            className="bg-foreground text-background text-[16px] font-medium px-[24px] py-[12px] rounded-[8px] hover:opacity-90 active:scale-95 transition-all shadow-[0px_0px_0px_1px_rgba(0,0,0,0.08)] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Start Deploying
          </button>
          <a href="#how-it-works">
            <button className="bg-white dark:bg-white/5 text-foreground text-[16px] font-medium px-[24px] py-[12px] rounded-[8px] hover:bg-gray-50 dark:hover:bg-white/10 active:scale-95 transition-all flex items-center gap-2 shadow-[0px_0px_0px_1px_rgba(0,0,0,0.08)] dark:shadow-[0px_0px_0px_1px_rgba(255,255,255,0.15)]">
              View Templates <ArrowRight className="w-5 h-5" />
            </button>
          </a>
        </div>
      </div>

      {/* About Us + Ad Comparison */}
      <div id="about" className="w-full max-w-[1200px] mx-auto mt-12 pt-16 px-6 md:px-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16 items-center text-left">
          <div className="flex flex-col">
            <h2 className="text-[40px] md:text-[48px] font-bold tracking-tight text-foreground mb-6 leading-[1.1]">
              Built for the <br />
              <span className="text-transparent bg-clip-text bg-linear-to-r from-[#0080FF] via-[#FF1493] to-[#00FFFF]">nuances of SEA.</span>
            </h2>
            <p className="text-[16px] md:text-[18px] text-gray-600 dark:text-gray-400 leading-relaxed mb-4">
              Global tools don't understand the complex cultural tapestry of Southeast Asia. A direct translation often misses the mark—or causes brand damage.
            </p>
            <p className="text-[16px] md:text-[18px] text-gray-600 dark:text-gray-400 leading-relaxed">
              JusAds empowers brands to scale seamlessly. We combine generative AI with deep, localized cultural models to ensure your message is not just heard, but felt.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Original */}
            <div className="bg-white dark:bg-white/5 rounded-xl p-4 border border-gray-200 dark:border-white/10 shadow-sm flex flex-col">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="text-sm font-bold text-foreground">Original Poster</h3>
                  <p className="text-[10px] text-gray-500 mt-1">Your uploaded ad</p>
                </div>
                <span className="bg-gray-100 dark:bg-white/10 text-gray-600 dark:text-gray-400 px-2 py-1 rounded-full text-[10px] font-semibold">Original</span>
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
                  <span className="font-bold mr-1">sanfewomxn</span>Hey, try our new serum! ✨
                </div>
              </div>
            </div>

            {/* Adapted */}
            <div className="bg-white dark:bg-white/5 rounded-xl p-4 border border-[#0a72ef]/30 shadow-[0_8px_30px_rgba(10,114,239,0.1)] flex flex-col">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="text-sm font-bold text-[#0a72ef]">Adapted Poster</h3>
                  <p className="text-[10px] text-gray-500 mt-1">MY Culture optimized</p>
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
                  <span className="font-bold mr-1 text-[#0a72ef]">sanfewomxn</span>Jom cuba serum baru! ✨
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Features ─────────────────────────────────────────────────────────────────

function Features() {
  const [nation, setNation] = useState<"MY" | "SG">("MY");

  return (
    <>
      <section id="how-it-works" className="max-w-[1200px] mx-auto px-6 lg:px-12 mt-[120px] mb-[80px]">
        <div className="text-center mb-12">
          <h2 className="text-[40px] font-semibold tracking-tight text-foreground mb-2 leading-tight">
            Your localization pipeline. Simplified.
          </h2>
          <p className="text-[18px] text-gray-600 dark:text-gray-400 leading-relaxed">
            From viral trend to localized, platform-ready ad in three steps.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            { step: "1 / TRENDING", color: "text-[#0080FF]", title: "Find what works.", desc: "Discover localized social media trends and identify high-performing content formats for your specific target market.", code: "> Fetching trending topics... [Done]" },
            { step: "2 / UPLOAD THEN GENERATE", color: "text-[#FF1493]", title: "Upload and transform.", desc: "Upload your base marketing assets and instantly generate culturally adapted variations tailored to local demographics.", code: "> Generating localized variants... [Done]" },
            { step: "3 / VALIDATE", color: "text-red-500", title: "Review and approve.", desc: "Ensure brand safety and cultural accuracy through our automated resonance checks before you deploy.", code: "> Running cultural resonance validation... Ready." },
          ].map(({ step, color, title, desc, code }) => (
            <div key={step} className="bg-white dark:bg-white/5 rounded-lg p-8 flex flex-col gap-4 shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] border-t border-gray-200 dark:border-white/10">
              <div className="flex flex-col gap-1">
                <span className={`text-[12px] uppercase tracking-widest font-medium ${color}`}>{step}</span>
                <h3 className="text-[24px] font-semibold text-foreground leading-snug">{title}</h3>
              </div>
              <p className="text-gray-600 dark:text-gray-400 text-[16px] leading-relaxed">{desc}</p>
              <div className="mt-auto pt-4">
                <div className="bg-gray-50 dark:bg-white/5 p-4 rounded text-[12px] font-mono text-gray-600 dark:text-gray-400 border border-gray-100 dark:border-white/5">
                  <code>{code}</code>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section id="features" className="max-w-[1200px] mx-auto px-6 lg:px-12 mt-[120px] mb-[120px]">
        <div className="text-center mb-12">
          <h2 className="text-[40px] font-semibold tracking-tight text-foreground mb-2 leading-tight">
            Everything you need to localize at scale.
          </h2>
          <p className="text-[20px] text-gray-600 dark:text-gray-400 leading-relaxed">
            Enterprise-grade AI tools built specifically for the SEA market.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Brand-Safe Trend Intelligence */}
          <div className="md:col-span-2 bg-white dark:bg-white/5 rounded-[12px] p-10 flex flex-col md:flex-row items-center gap-10 shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] border border-gray-200 dark:border-white/10">
            <div className="flex-1">
              <h3 className="text-[24px] font-semibold text-foreground mb-4 leading-snug">Brand-Safe Trend Intelligence.</h3>
              <p className="text-[16px] text-gray-600 dark:text-gray-400 leading-relaxed">
                Monitor local TikTok and YouTube trends filtered securely for brand safety. Capitalize on viral moments without risking your brand's reputation in sensitive markets.
              </p>
            </div>
            <div className="flex-1 w-full bg-gray-50 dark:bg-white/5 rounded-lg p-8 flex flex-col gap-4 font-mono">
              {["#RayaPrep", "#LocalCoffee"].map(tag => (
                <div key={tag} className="flex justify-between items-center p-3 bg-white dark:bg-white/5 border border-gray-100 dark:border-white/5 rounded shadow-sm">
                  <span className="text-foreground text-[14px]">{tag}</span>
                  <span className="bg-[#0080FF]/10 text-[#0080FF] px-2 py-1 rounded text-[10px] uppercase font-bold">Safe</span>
                </div>
              ))}
            </div>
          </div>

          {/* Nation Support Engine */}
          <div className="bg-white dark:bg-white/5 rounded-[12px] p-8 flex flex-col gap-8 shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] border border-gray-200 dark:border-white/10">
            <div>
              <h3 className="text-[24px] font-semibold text-foreground mb-2 leading-snug">Nation Support Engine.</h3>
              <p className="text-[16px] text-gray-600 dark:text-gray-400 leading-relaxed">Instantly adapt branding, video assets, and context for local audiences.</p>
            </div>
            <div className="mt-auto">
              <div className="flex bg-gray-100 dark:bg-white/10 p-1 rounded-full w-full mb-4 relative">
                <div className="absolute top-1 bottom-1 w-[calc(50%-4px)] rounded-full bg-[#0080FF] transition-all duration-300 shadow-sm" style={{ left: nation === "MY" ? "4px" : "calc(50%)" }} />
                <button onClick={() => setNation("MY")} className={`flex-1 text-xs py-2 rounded-full font-bold transition-all relative z-10 ${nation === "MY" ? "text-white" : "text-gray-500 hover:text-foreground"}`}>Malaysia</button>
                <button onClick={() => setNation("SG")} className={`flex-1 text-xs py-2 rounded-full font-bold transition-all relative z-10 ${nation === "SG" ? "text-white" : "text-gray-500 hover:text-foreground"}`}>Singapore</button>
              </div>
              <div className="p-4 bg-gray-50 dark:bg-white/5 rounded border border-gray-100 dark:border-white/5 text-sm mb-2 text-gray-600 dark:text-gray-400">
                "The ultimate refreshing drink for a hot day."
              </div>
              <div className={`p-4 rounded border text-sm font-medium transition-colors duration-500 ${nation === "MY" ? "bg-blue-50 dark:bg-[#0080FF]/10 border-blue-200 dark:border-[#0080FF]/20 text-blue-700 dark:text-[#0080FF]" : "bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/20 text-orange-700 dark:text-orange-400"}`}>
                {nation === "MY" ? '"Minuman paling ngam waktu panas lit lit."' : '"The perfect thirst-quencher for this blazing heat, lah."'}
              </div>
            </div>
          </div>

          {/* High-Fidelity Gen AI */}
          <div className="bg-white dark:bg-white/5 rounded-[12px] p-8 flex flex-col gap-8 shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] border border-gray-200 dark:border-white/10">
            <div>
              <h3 className="text-[24px] font-semibold text-foreground mb-2 leading-snug">High-Fidelity Gen AI.</h3>
              <p className="text-[16px] text-gray-600 dark:text-gray-400 leading-relaxed">Generate stunning, culturally aligned visuals that feel truly authentic to the local market.</p>
            </div>
            <div className="mt-auto relative flex items-center justify-center bg-gray-900 rounded-lg h-[180px] overflow-hidden border border-white/5">
              <div className="absolute inset-0 z-0 opacity-80 mix-blend-screen">
                <div className="absolute top-[-50%] left-[-20%] w-[80%] h-[150%] bg-[#0080FF] rounded-full filter blur-2xl opacity-40 animate-pulse" />
                <div className="absolute top-[10%] right-[-20%] w-[70%] h-[120%] bg-[#FF1493] rounded-full filter blur-2xl opacity-30 animate-pulse" style={{ animationDelay: "1s" }} />
                <div className="absolute bottom-[-50%] left-[20%] w-[80%] h-full bg-[#00FFFF] rounded-full filter blur-2xl opacity-30 animate-pulse" style={{ animationDelay: "2s" }} />
              </div>
              <div className="absolute inset-0 flex items-center justify-center gap-[6px] opacity-60 z-10">
                {[3,6,10,5,12,8,0,8,12,5,10,6,3].map((h, i) => (
                  <div key={i} className={`w-1.5 bg-[#FF1493] rounded-full animate-pulse ${h === 0 ? "w-[40px]" : ""}`} style={{ height: h ? `${h * 4}px` : undefined, animationDelay: `${i * 0.1}s` }} />
                ))}
              </div>
              <PlayCircle className="relative z-10 text-white w-12 h-12 hover:scale-110 transition-transform cursor-pointer drop-shadow-lg" />
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

// ─── Pricing ──────────────────────────────────────────────────────────────────

function Pricing({ onAuthAction }: { onAuthAction: AuthAction }) {
  const navigate = useNavigate();
  const { isAuthenticated, onOpenLogin, status } = onAuthAction;
  const isLoading = status === "loading";

  function handleCTA() {
    if (isAuthenticated) navigate("/dashboard");
    else onOpenLogin();
  }

  return (
    <section id="pricing" className="max-w-[1200px] mx-auto px-6 lg:px-12 mt-[120px] mb-[120px]">
      <div className="text-center mb-16">
        <h2 className="text-[40px] font-semibold tracking-tight text-foreground mb-4 leading-tight">Simple, transparent pricing</h2>
        <p className="text-[20px] text-gray-600 dark:text-gray-400 max-w-[600px] mx-auto leading-relaxed">Start for free, upgrade when you need to localize at scale.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-[900px] mx-auto">
        {/* Hobby */}
        <div className="bg-white dark:bg-white/5 rounded-[12px] p-8 flex flex-col shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] border border-gray-200 dark:border-white/10">
          <div className="mb-8">
            <h3 className="text-[20px] font-semibold text-foreground mb-2">Hobby</h3>
            <p className="text-[14px] text-gray-600 dark:text-gray-400 h-10">Perfect for experimenting with AI localization.</p>
            <div className="mt-6 flex items-baseline gap-1">
              <span className="text-[48px] font-bold text-foreground tracking-tight">$0</span>
              <span className="text-[16px] text-gray-500 font-medium">/month</span>
            </div>
          </div>
          <button onClick={handleCTA} disabled={isLoading} className="w-full bg-white dark:bg-white/5 text-foreground text-[14px] font-medium py-[10px] rounded-[6px] hover:bg-gray-50 dark:hover:bg-white/10 transition-all mb-8 shadow-[0px_0px_0px_1px_rgba(0,0,0,0.08)] dark:shadow-[0px_0px_0px_1px_rgba(255,255,255,0.15)] disabled:opacity-50">
            Start Deploying
          </button>
          <div className="flex flex-col gap-4 mt-auto">
            {["5 AI transcreations per month", "Standard 720p export", "Community support"].map(f => (
              <div key={f} className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-foreground shrink-0" />
                <span className="text-[14px] text-gray-600 dark:text-gray-400">{f}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Pro */}
        <div className="bg-white dark:bg-white/5 rounded-[12px] p-8 flex flex-col shadow-[rgba(0,0,0,0.08)_0_8px_30px,0_0_0_1px_#0a72ef] border border-[#0a72ef]/50 relative">
          <div className="absolute top-[12px] left-1/2 -translate-x-1/2 bg-[#0a72ef] text-white px-3 py-1 rounded-full text-[12px] font-bold tracking-widest uppercase">Most Popular</div>
          <div className="mb-8 mt-2">
            <h3 className="text-[20px] font-semibold text-foreground mb-2">Pro</h3>
            <p className="text-[14px] text-gray-600 dark:text-gray-400 h-10">For marketers who need to localize at scale.</p>
            <div className="mt-6 flex items-baseline gap-1">
              <span className="text-[48px] font-bold text-foreground tracking-tight">$29</span>
              <span className="text-[16px] text-gray-500 font-medium">/month</span>
            </div>
          </div>
          <button onClick={handleCTA} disabled={isLoading} className="w-full bg-foreground text-background text-[14px] font-medium py-[10px] rounded-[6px] hover:opacity-90 transition-all mb-8 disabled:opacity-50">
            Upgrade to Pro
          </button>
          <div className="flex flex-col gap-4 mt-auto">
            {["Unlimited AI transcreations", "4K raw export quality", "Priority 24/7 support", "Custom brand voice guidelines"].map(f => (
              <div key={f} className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-[#0a72ef] shrink-0" />
                <span className="text-[14px] text-gray-600 dark:text-gray-400">{f}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── FAQ ──────────────────────────────────────────────────────────────────────

const FAQS = [
  { question: "What languages and dialects do you currently support?", answer: "We currently offer deep localization models for Malaysian (Bahasa Melayu, Manglish, Tamil, local Mandarin dialects) and Singaporean (Singlish, local Mandarin) markets. We are actively expanding to Indonesia and Thailand." },
  { question: "How does JusAds ensure brand safety?", answer: "Our Trend Intelligence engine specifically filters out sensitive, political, or controversial local trends. Before any asset is exported, it passes through our automated cultural resonance check to ensure strict brand safety." },
  { question: "Do I need technical skills to use the platform?", answer: "Not at all. JusAds is designed for marketing teams. You simply upload your base English assets, select your target demographic, and our AI pipeline handles the transcreation, visual masking, and rendering automatically." },
];

function Faq() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section id="faq" className="max-w-[800px] mx-auto px-6 lg:px-12 mt-[120px] mb-[160px]">
      <div className="text-center mb-12">
        <h2 className="text-[40px] font-semibold tracking-tight text-foreground mb-4 leading-tight">Frequently asked questions</h2>
        <p className="text-[18px] text-gray-600 dark:text-gray-400">Everything you need to know about scaling your localization.</p>
      </div>
      <div className="space-y-4">
        {FAQS.map((faq, i) => (
          <div key={i} className="bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl overflow-hidden shadow-sm">
            <button className="w-full px-6 py-5 flex items-center justify-between text-left focus:outline-none" onClick={() => setOpenIndex(openIndex === i ? null : i)}>
              <span className="text-[16px] font-medium text-foreground">{faq.question}</span>
              <ChevronDown className={`w-5 h-5 text-gray-500 transition-transform duration-300 ${openIndex === i ? "rotate-180" : ""}`} />
            </button>
            <div className={`px-6 overflow-hidden transition-all duration-300 ease-in-out ${openIndex === i ? "max-h-96 pb-5 opacity-100" : "max-h-0 opacity-0"}`}>
              <p className="text-[15px] text-gray-600 dark:text-gray-400 leading-relaxed">{faq.answer}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ─── Footer ───────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="w-full border-t border-black/8 dark:border-white/8 bg-background/50 backdrop-blur-md mt-24">
      <div className="w-full px-6 md:px-12 py-12">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-8">
          <div className="flex flex-col gap-4">
            <Link to="/" className="flex items-center gap-2">
              <img src="/logo-black.png" alt="JusAds Logo" className="h-8 w-auto block dark:hidden" />
              <img src="/logo-white.png" alt="JusAds Logo" className="h-8 w-auto hidden dark:block" />
              <span className="font-semibold text-[16px] tracking-tight text-foreground">JusAds</span>
            </Link>
            <p className="text-[14px] text-gray-500 dark:text-gray-400">© {new Date().getFullYear()} JusAds. Built for the nuances of SEA.</p>
          </div>
          <div className="flex gap-8">
            <div className="flex flex-col gap-3">
              <h4 className="text-[14px] font-semibold text-foreground">Product</h4>
              <a href="#how-it-works" className="text-[14px] text-gray-500 hover:text-foreground dark:text-gray-400 transition-colors">How it works</a>
              <a href="#pricing"      className="text-[14px] text-gray-500 hover:text-foreground dark:text-gray-400 transition-colors">Pricing</a>
              <a href="#faq"          className="text-[14px] text-gray-500 hover:text-foreground dark:text-gray-400 transition-colors">FAQ</a>
            </div>
            <div className="flex flex-col gap-3">
              <h4 className="text-[14px] font-semibold text-foreground">Company</h4>
              <a href="#about" className="text-[14px] text-gray-500 hover:text-foreground dark:text-gray-400 transition-colors">About Us</a>
              <a href="https://www.linkedin.com/company/95728322" target="_blank" rel="noreferrer" className="text-[14px] text-gray-500 hover:text-foreground dark:text-gray-400 transition-colors">LinkedIn</a>
              <a href="mailto:hello@jusads.com" className="text-[14px] text-gray-500 hover:text-foreground dark:text-gray-400 transition-colors">Contact</a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const { isAuthenticated, status } = useAuth();
  const [isLoginOpen, setIsLoginOpen] = useState(false);

  const onAuthAction: AuthAction = {
    isAuthenticated,
    onOpenLogin: () => setIsLoginOpen(true),
    status,
  };

  return (
    <div className="relative pb-24 overflow-x-hidden min-h-dvh bg-background transition-colors duration-500">
      {/* Aurora background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute inset-0 opacity-[0.03] dark:opacity-[0.15] transition-opacity duration-500" style={{ backgroundImage: "radial-gradient(currentColor 1px, transparent 1px)", backgroundSize: "40px 40px" }} />
        <div className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vh] bg-[#0080FF] rounded-full mix-blend-multiply dark:mix-blend-screen filter blur-[120px] opacity-30 dark:opacity-20 animate-pulse" />
        <div className="absolute top-[20%] right-[-10%] w-[40vw] h-[60vh] bg-[#FF1493] rounded-full mix-blend-multiply dark:mix-blend-screen filter blur-[150px] opacity-10 dark:opacity-20 animate-pulse" style={{ animationDelay: "1s" }} />
        <div className="absolute bottom-[-10%] left-[20%] w-[50vw] h-[50vh] bg-[#00FFFF] rounded-full mix-blend-multiply dark:mix-blend-screen filter blur-[120px] opacity-20 dark:opacity-20 animate-pulse" style={{ animationDelay: "2s" }} />
      </div>

      <div className="relative z-10">
        <Header onAuthAction={onAuthAction} />
        <Hero onAuthAction={onAuthAction} />
        <Features />
        <Pricing onAuthAction={onAuthAction} />
        <Faq />
        <Footer />
        <FloatingButton />
      </div>

      <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} />
    </div>
  );
}
