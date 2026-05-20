import { useAuth } from "../hooks/useAuth";
import { Mail, User as UserIcon, Shield, Globe, Calendar } from "lucide-react";

export default function DashboardProfile() {
  const { user, picture } = useAuth();
  const profile = user?.profile;

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

  return (
    <div className="flex-1 overflow-y-auto flex flex-col gap-10 p-10 max-w-3xl mx-auto w-full">
      {/* ── Profile Header ────────────────────────────────────────────────── */}
      <div className="flex items-center gap-6">
        <div className="relative shrink-0">
          <div className="w-20 h-20 rounded-full overflow-hidden ring-2 ring-gray-200 dark:ring-white/10 shadow-md">
            {picture ? (
              <img
                src={picture}
                alt="Profile photo"
                className="w-full h-full object-cover"
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-linear-to-br from-[#7B2FBE] to-[#FF6B9D] text-white text-2xl font-bold">
                {initials}
              </div>
            )}
          </div>
          <span className="absolute bottom-0 right-0 w-4 h-4 rounded-full bg-[#00D4AA] border-2 border-white dark:border-[#0a0a0f]" />
        </div>

        <div className="flex flex-col gap-1">
          <h1 className="text-[28px] font-bold tracking-[-0.03em] text-[#171717] dark:text-white">
            {displayName}
          </h1>
          <p className="text-[15px] text-gray-500 dark:text-gray-400 font-medium">
            {email ?? "No email available"}
          </p>
        </div>
      </div>

      {/* ── Account Details ───────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4">
        <h2 className="text-[13px] uppercase font-bold tracking-wider text-gray-400 dark:text-gray-500">
          Account Details
        </h2>

        <div className="rounded-[12px] border border-gray-200 dark:border-white/10 bg-white dark:bg-[#111116] divide-y divide-gray-100 dark:divide-white/5 overflow-hidden shadow-sm">
          <InfoRow icon={<UserIcon size={16} />} label="Full Name"  value={displayName} />
          <InfoRow icon={<Mail size={16} />}     label="Email"      value={email ?? "—"} />
          <InfoRow icon={<Shield size={16} />}   label="User ID"    value={sub ?? "—"} mono />
          <InfoRow icon={<Globe size={16} />}    label="Provider"   value="Google (via AWS Cognito)" />
          {authTime   && <InfoRow icon={<Calendar size={16} />} label="Last Authenticated" value={authTime} />}
          {tokenExpiry && <InfoRow icon={<Calendar size={16} />} label="Session Expires"   value={tokenExpiry} />}
        </div>
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
    <div className="flex items-center gap-4 px-5 py-4">
      <span className="text-gray-400 dark:text-gray-500 shrink-0">{icon}</span>
      <span className="text-[13px] font-medium text-gray-500 dark:text-gray-400 w-36 shrink-0">
        {label}
      </span>
      <span className={`text-[14px] text-[#171717] dark:text-white flex-1 truncate ${mono ? "font-mono text-[12px]" : "font-medium"}`}>
        {value}
      </span>
    </div>
  );
}
