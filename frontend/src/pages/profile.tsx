import { useRef, useState, useEffect } from "react";
import { useAuth } from "../hooks/useAuth";
import { Mail, User as UserIcon, Shield, Globe, Calendar, LogOut, Building2, Package, MonitorPlay, Pencil } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";

import {
  disconnectZernioConnection,
  getBusinessProfile,
  getZernioConnection,
  saveZernioConnection,
} from "@/services/accountService";
import type { BusinessProfile, ZernioConnection } from "@/models/account";

gsap.registerPlugin(useGSAP);

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

  // Zernio API Key state
  const [zernioKeyInput, setZernioKeyInput] = useState("");
  const [zernioStatus, setZernioStatus] = useState<ZernioConnection>({
    has_key: false,
    masked_key: "",
    connected: false,
    accounts: [],
    message: "",
  });
  const [loadingZernio, setLoadingZernio] = useState(true);
  const [savingZernioKey, setSavingZernioKey] = useState(false);

  useEffect(() => {
    if (!email) return;
    (async () => {
      try {
        setBusinessProfile(await getBusinessProfile());
      } catch {
        // Non-fatal
      } finally {
        setLoadingProfile(false);
      }
    })();
  }, [email]);

  const fetchZernioStatus = async () => {
    try {
      setZernioStatus(await getZernioConnection());
    } catch {
      // Non-fatal
    } finally {
      setLoadingZernio(false);
    }
  };

  useEffect(() => {
    if (!email) return;
    // Defer the stateful request until after this render commits.  Calling a
    // state-changing helper synchronously from an effect causes a cascading
    // render and is flagged by React's hooks lint rule.
    const timer = window.setTimeout(() => {
      void fetchZernioStatus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [email]);

  const handleSaveZernioKey = async () => {
    if (!zernioKeyInput.trim()) return;
    setSavingZernioKey(true);
    try {
      setZernioStatus(await saveZernioConnection(zernioKeyInput.trim()));
      setZernioKeyInput("");
    } catch {
      alert("Network error saving Zernio API Key");
    } finally {
      setSavingZernioKey(false);
    }
  };

  const handleDisconnectZernio = async () => {
    if (!confirm("Disconnect your Zernio account?")) return;
    try {
      await disconnectZernioConnection();
      setZernioStatus({
        has_key: false,
        masked_key: "",
        connected: false,
        accounts: [],
        message: "Zernio account disconnected.",
      });
    } catch {
      // Non-fatal
    }
  };

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
          <h1 className="font-bold tracking-[-0.03em] text-text-heading">
            {displayName}
          </h1>
          <p className="text-[15px] text-text-caption font-medium">
            {email ?? "No email available"}
          </p>
        </div>
      </div>

      {/* ── Zernio Social Account Connection ───────────────────────────────── */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="account-label text-code-sm uppercase font-bold tracking-wider text-text-caption">
            Social Media Publishing (Zernio Account)
          </h3>
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${
            zernioStatus.connected
              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
              : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
          }`}>
            {zernioStatus.connected ? "CONNECTED" : "NOT CONNECTED"}
          </span>
        </div>

        <div className="rounded-[12px] border border-border-default bg-surface-card p-6 card-shadow retina-border flex flex-col gap-5">
          <div>
            <p className="text-sm font-bold text-text-heading">
              Zernio Account Integration
            </p>
            <p className="text-xs text-text-caption mt-0.5">
              Connect your Zernio account using your API key to automatically publish generated ads to your social channels.
            </p>
          </div>

          {loadingZernio ? (
            <p className="text-xs text-text-muted animate-pulse">Checking Zernio connection...</p>
          ) : zernioStatus.connected ? (
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between p-3.5 rounded-lg border border-border-default bg-surface-inset">
                <div className="flex items-center gap-3">
                  <span className="text-emerald-500 font-bold">✓</span>
                  <div>
                    <p className="text-xs font-bold text-text-heading">Active API Key</p>
                    <p className="text-xs font-mono text-text-caption">{zernioStatus.masked_key}</p>
                  </div>
                </div>
                <button
                  onClick={handleDisconnectZernio}
                  className="text-xs text-red-500 hover:text-red-600 font-medium px-3 py-1 hover:bg-red-500/10 rounded transition-colors cursor-pointer"
                >
                  Disconnect
                </button>
              </div>

              <div>
                <p className="text-xs font-semibold text-text-caption mb-2">Connected Social Channels</p>
                {zernioStatus.accounts && zernioStatus.accounts.length > 0 ? (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {zernioStatus.accounts.map((ch) => (
                      <div key={ch.name} className="flex items-center gap-2.5 rounded-lg border border-border-default bg-surface-inset p-3">
                        <span className="text-base">{ch.icon}</span>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-text-heading truncate">{ch.name}</p>
                          <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">{ch.status}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-3 rounded-lg border border-dashed border-border-subtle bg-surface-inset text-center">
                    <p className="text-xs text-text-caption">No social media channels linked to this Zernio API Key yet.</p>
                    <a
                      href="https://zernio.com"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-accent-blue hover:underline font-medium inline-block mt-1"
                    >
                      Manage channels on Zernio Dashboard ↗
                    </a>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-text-heading">Enter Zernio API Key</span>
                <a
                  href="https://zernio.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent-blue hover:underline font-medium inline-flex items-center gap-1"
                >
                  Don't have a key? Get one at Zernio ↗
                </a>
              </div>

              <div className="flex gap-2">
                <input
                  type="password"
                  value={zernioKeyInput}
                  onChange={(e) => setZernioKeyInput(e.target.value)}
                  placeholder="Enter your Zernio API Key (e.g. zern_live_...)"
                  className="flex-1 rounded-lg border border-border-default bg-background px-4 py-2.5 text-xs text-text-heading placeholder:text-text-caption focus:outline-none focus:ring-2 focus:ring-accent-blue/20 focus:border-accent-blue font-mono"
                />
                <button
                  onClick={handleSaveZernioKey}
                  disabled={savingZernioKey || !zernioKeyInput.trim()}
                  className="px-4 py-2.5 rounded-lg bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 transition-colors disabled:opacity-50 cursor-pointer shrink-0"
                >
                  {savingZernioKey ? "Connecting..." : "Save & Connect"}
                </button>
              </div>
            </div>
          )}
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
