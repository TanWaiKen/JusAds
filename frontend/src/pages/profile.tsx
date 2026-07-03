import { useRef, useState, useEffect } from "react";
import { useAuth } from "../hooks/useAuth";
import { Mail, User as UserIcon, Shield, Globe, Calendar, LogOut, Building2, Package, MonitorPlay, Pencil } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";

gsap.registerPlugin(useGSAP);

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

interface BusinessProfile {
  company_name: string;
  product_category: string;
  product_description: string;
  target_platforms: string[];
  target_markets: string[];
}

export default function DashboardProfile() {
  const { user, picture, logout } = useAuth();
  const profile = user?.profile;
  const containerRef = useRef<HTMLDivElement>(null);

  const displayName = profile?.name ?? "—";
  const email = profile?.email as string | undefined;
  const sub = profile?.sub;
  const initials = displayName !== "—" ? displayName.slice(0, 2).toUpperCase() : "?";

  const authTime = profile?.auth_time
    ? new Date(Number(profile.auth_time) * 1000).toLocaleString()
    : null;
  const tokenExpiry = user?.expires_at
    ? new Date(user.expires_at * 1000).toLocaleString()
    : null;

  // Business profile state
  const [businessProfile, setBusinessProfile] = useState<BusinessProfile | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(true);

  useEffect(() => {
    if (!email) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/profile/${encodeURIComponent(email)}`);
        if (res.ok) {
          setBusinessProfile(await res.json());
        }
      } catch {
        // Non-fatal
      } finally {
        setLoadingProfile(false);
      }
    })();
  }, [email]);

  // GSAP animation for profile elements
  useGSAP(() => {
    const tl = gsap.timeline({ defaults: { duration: 0.5, ease: "power3.out" } });

    tl.from(".profile-header", {
      y: -15,
      autoAlpha: 0,
      duration: 0.6
    });

    tl.from(".account-label", {
      autoAlpha: 0,
      duration: 0.4
    }, "-=0.2");

    tl.from(".info-row-item", {
      x: -20,
      autoAlpha: 0,
      stagger: 0.06,
      duration: 0.5
    }, "-=0.3");
  }, { scope: containerRef });

  return (
    <div ref={containerRef} className="flex flex-col gap-10 p-10 max-w-3xl mx-auto w-full font-hanken">
      {/* ── Profile Header ────────────────────────────────────────────────── */}
      <div className="profile-header flex items-center gap-6">
        <div className="relative shrink-0">
          <div className="w-20 h-20 rounded-full overflow-hidden ring-2 ring-border-default shadow-md retina-border">
            {picture ? (
              <img
                src={picture}
                alt="Profile photo"
                className="w-full h-full object-cover"
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-gray-200 dark:bg-white/10 text-gray-700 dark:text-gray-300 text-2xl font-bold">
                {initials}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <h2 className="text-[24px] font-bold tracking-[-0.03em] text-text-heading">
            {displayName}
          </h2>
          <p className="text-[15px] text-text-caption font-medium">
            {email ?? "No email available"}
          </p>
        </div>
      </div>

      {/* ── Business Profile ──────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="account-label text-code-sm uppercase font-bold tracking-wider text-text-caption">
            Business Profile
          </h3>
          {businessProfile && (
            <a
              href="/dashboard/onboarding"
              className="flex items-center gap-1 text-xs text-accent-blue hover:underline"
            >
              <Pencil size={12} />
              Edit
            </a>
          )}
        </div>

        {loadingProfile ? (
          <div className="rounded-[12px] border border-border-default bg-surface-card p-6">
            <p className="text-sm text-text-muted animate-pulse">Loading business profile...</p>
          </div>
        ) : businessProfile ? (
          <div className="rounded-[12px] border border-border-default bg-surface-card divide-y divide-gray-100 dark:divide-white/5 overflow-hidden card-shadow retina-border">
            <InfoRow icon={<Building2 size={16} />} label="Company" value={businessProfile.company_name} />
            <InfoRow icon={<Package size={16} />} label="Category" value={businessProfile.product_category} />
            {businessProfile.product_description && (
              <InfoRow icon={<Package size={16} />} label="Description" value={businessProfile.product_description} />
            )}
            <InfoRow icon={<MonitorPlay size={16} />} label="Platforms" value={businessProfile.target_platforms.join(", ")} />
            <InfoRow icon={<Globe size={16} />} label="Markets" value={businessProfile.target_markets.join(", ")} />
          </div>
        ) : (
          <div className="rounded-[12px] border border-dashed border-border-default bg-surface-card p-6 text-center">
            <p className="text-sm text-text-muted mb-3">No business profile set up yet.</p>
            <a
              href="/dashboard/onboarding"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Complete Setup
            </a>
          </div>
        )}
      </div>

      {/* ── Account Details ───────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4">
        <h3 className="account-label text-code-sm uppercase font-bold tracking-wider text-text-caption">
          Account Details
        </h3>

        <div className="rounded-[12px] border border-border-default bg-surface-card divide-y divide-gray-100 dark:divide-white/5 overflow-hidden card-shadow retina-border">
          <InfoRow icon={<UserIcon size={16} />} label="Full Name"  value={displayName} />
          <InfoRow icon={<Mail size={16} />}     label="Email"      value={email ?? "—"} />
          <InfoRow icon={<Shield size={16} />}   label="User ID"    value={sub ?? "—"} mono />
          <InfoRow icon={<Globe size={16} />}    label="Provider"   value="Google (via AWS Cognito)" />
          {authTime   && <InfoRow icon={<Calendar size={16} />} label="Last Authenticated" value={authTime} />}
          {tokenExpiry && <InfoRow icon={<Calendar size={16} />} label="Session Expires"   value={tokenExpiry} />}
        </div>
      </div>

      {/* ── Log Out ───────────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4">
        <button
          onClick={() => void logout()}
          className="flex items-center justify-center gap-2 w-full rounded-xl border border-border-default px-4 py-3 text-label-ui font-bold text-error hover:bg-error/5 active:scale-[0.98] transition-all cursor-pointer"
        >
          <LogOut size={18} />
          Log Out
        </button>
      </div>
    </div>
  );
}

// ─── InfoRow ──────────────────────────────────────────────────────────────────

interface InfoRowProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
}

function InfoRow({ icon, label, value, mono }: InfoRowProps) {
  return (
    <div className="info-row-item flex items-center gap-4 px-5 py-4 hover:bg-surface-inset transition-colors duration-150">
      <span className="text-text-caption shrink-0">{icon}</span>
      <span className="text-code-sm font-medium text-text-caption w-36 shrink-0">
        {label}
      </span>
      <span className={`text-label-ui text-text-heading flex-1 truncate ${mono ? "font-mono text-[12px]" : "font-medium"}`}>
        {value}
      </span>
    </div>
  );
}
