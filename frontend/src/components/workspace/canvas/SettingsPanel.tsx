/**
 * SettingsPanel — Two-tab settings popup (Vercel-inspired design).
 *
 * Tab 1: Target Consumer — who the ad is reaching.
 * Tab 2: Generation Settings — how the ad is made.
 *
 * All values flow into the generation request and conditionally affect
 * localization, compliance, voice selection, and content style.
 */

import React, { useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { X } from "lucide-react";
import { PlatformSelector } from "@/components/workspace/canvas/PlatformSelector";
import type { TargetPlatform, TargetEthnicity } from "@/services/generationApi";

gsap.registerPlugin(useGSAP);

// ─── Types ───────────────────────────────────────────────────────────────────

export type AgeGroup = "gen_z" | "millennial" | "gen_x" | "baby_boomer" | "all_ages";
export type Gender = "male" | "female" | "mixed";
export type Market = "malaysia" | "singapore";
export type Language = "ms" | "en" | "zh" | "ta" | "auto";

export interface GenerationSettings {
  targetPlatform: TargetPlatform | null;
  targetEthnicity: TargetEthnicity;
  ageGroup: AgeGroup;
  gender: Gender;
  market: Market;
  language: Language;
  productName: string;
  productCategory: string;
  complianceEnabled: boolean;
  videoV2Enabled: boolean;
}

interface SettingsPanelProps {
  settings: GenerationSettings;
  onUpdate: (patch: Partial<GenerationSettings>) => void;
  onClose: () => void;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

interface OptionButtonProps {
  label: string;
  selected: boolean;
  onClick: () => void;
}

function OptionButton({ label, selected, onClick }: OptionButtonProps): React.ReactElement {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
        selected
          ? "bg-[#171717] text-white shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px]"
          : "bg-white text-[#171717] shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] hover:bg-[#fafafa]"
      }`}
      aria-pressed={selected}
    >
      {label}
    </button>
  );
}

interface ToggleRowProps {
  label: string;
  description: string;
  enabled: boolean;
  onToggle: () => void;
}

function ToggleRow({ label, description, enabled, onToggle }: ToggleRowProps): React.ReactElement {
  return (
    <div className="flex items-center justify-between rounded-lg p-3 shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px]">
      <div className="flex flex-col gap-0.5">
        <span className="text-xs font-semibold text-[#171717]">{label}</span>
        <span className="text-[10px] text-[#666666]">{description}</span>
      </div>
      <button
        type="button"
        onClick={onToggle}
        className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
          enabled ? "bg-[#171717]" : "bg-[#ebebeb]"
        }`}
        role="switch"
        aria-checked={enabled}
      >
        <span
          className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-transform ${
            enabled ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}

// ─── Tab: Target Consumer ────────────────────────────────────────────────────

function TargetConsumerTab({
  settings,
  onUpdate,
}: {
  settings: GenerationSettings;
  onUpdate: (patch: Partial<GenerationSettings>) => void;
}): React.ReactElement {
  return (
    <div className="flex flex-col gap-5">
      {/* Market */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-[#171717] tracking-tight">Market</span>
        <div className="flex gap-2">
          {([
            { value: "malaysia", label: "🇲🇾 Malaysia" },
            { value: "singapore", label: "🇸🇬 Singapore" },
          ] as { value: Market; label: string }[]).map((opt) => (
            <OptionButton
              key={opt.value}
              label={opt.label}
              selected={settings.market === opt.value}
              onClick={() => onUpdate({ market: opt.value })}
            />
          ))}
        </div>
      </div>

      {/* Ethnicity */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-[#171717] tracking-tight">Target Ethnicity</span>
        <div className="flex flex-wrap gap-2">
          {([
            { value: "all", label: "All (Mixed)" },
            { value: "malay", label: "Malay" },
            { value: "chinese", label: "Chinese" },
            { value: "indian", label: "Indian" },
          ] as { value: TargetEthnicity; label: string }[]).map((opt) => (
            <OptionButton
              key={opt.value}
              label={opt.label}
              selected={settings.targetEthnicity === opt.value}
              onClick={() => onUpdate({ targetEthnicity: opt.value })}
            />
          ))}
        </div>
        <p className="text-[10px] text-[#666666]">
          {settings.targetEthnicity === "malay" && "Halal-friendly: modest dress, no pork/alcohol/gambling."}
          {settings.targetEthnicity === "chinese" && "Pork/alcohol OK if relevant; CNY themes; Mandarin copy."}
          {settings.targetEthnicity === "indian" && "No beef; veg-friendly; Deepavali themes; Tamil/English."}
          {settings.targetEthnicity === "all" && "Universally inclusive — safe for all audiences."}
        </p>
      </div>

      {/* Age Group */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-[#171717] tracking-tight">Age Group</span>
        <div className="flex flex-wrap gap-2">
          {([
            { value: "gen_z", label: "Gen Z (18–27)" },
            { value: "millennial", label: "Millennial (28–43)" },
            { value: "gen_x", label: "Gen X (44–59)" },
            { value: "baby_boomer", label: "Baby Boomer (60+)" },
            { value: "all_ages", label: "All Ages" },
          ] as { value: AgeGroup; label: string }[]).map((opt) => (
            <OptionButton
              key={opt.value}
              label={opt.label}
              selected={settings.ageGroup === opt.value}
              onClick={() => onUpdate({ ageGroup: opt.value })}
            />
          ))}
        </div>
        <p className="text-[10px] text-[#666666]">
          {settings.ageGroup === "gen_z" && "Trendy, informal, snappy. TikTok-native. Manglish/slang OK."}
          {settings.ageGroup === "millennial" && "Digital-savvy, aspirational lifestyle. Mix of formal and casual."}
          {settings.ageGroup === "gen_x" && "Value-driven, family. More formal Bahasa Melayu preferred."}
          {settings.ageGroup === "baby_boomer" && "Respectful, formal language. Bahasa Melayu. Traditional values."}
          {settings.ageGroup === "all_ages" && "Neutral, family-friendly, accessible to all generations."}
        </p>
      </div>

      {/* Gender */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-[#171717] tracking-tight">Voiceover Gender</span>
        <div className="flex gap-2">
          {([
            { value: "female", label: "Female" },
            { value: "male", label: "Male" },
            { value: "mixed", label: "Mixed / Auto" },
          ] as { value: Gender; label: string }[]).map((opt) => (
            <OptionButton
              key={opt.value}
              label={opt.label}
              selected={settings.gender === opt.value}
              onClick={() => onUpdate({ gender: opt.value })}
            />
          ))}
        </div>
      </div>

      {/* Language */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-[#171717] tracking-tight">Copy Language</span>
        <div className="flex flex-wrap gap-2">
          {([
            { value: "auto", label: "Auto (match audience)" },
            { value: "ms", label: "Bahasa Melayu" },
            { value: "en", label: "English" },
            { value: "zh", label: "中文 Mandarin" },
            { value: "ta", label: "தமிழ் Tamil" },
          ] as { value: Language; label: string }[]).map((opt) => (
            <OptionButton
              key={opt.value}
              label={opt.label}
              selected={settings.language === opt.value}
              onClick={() => onUpdate({ language: opt.value })}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Tab: Generation Settings ────────────────────────────────────────────────

function GenerationTab({
  settings,
  onUpdate,
}: {
  settings: GenerationSettings;
  onUpdate: (patch: Partial<GenerationSettings>) => void;
}): React.ReactElement {
  return (
    <div className="flex flex-col gap-5">
      {/* Platform */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-[#171717] tracking-tight">Target Platform</span>
        <PlatformSelector selected={settings.targetPlatform} onSelect={(p) => onUpdate({ targetPlatform: p })} />
      </div>

      {/* Product context */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-[#171717] tracking-tight">Product / Brand Name</span>
        <input
          type="text"
          value={settings.productName}
          onChange={(e) => onUpdate({ productName: e.target.value })}
          placeholder="e.g. Kopi Luwak Premium"
          className="rounded-md px-3 py-2 text-xs text-[#171717] shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] placeholder:text-[#808080] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsla(212,100%,48%,1)]"
        />
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-[#171717] tracking-tight">Product Category</span>
        <select
          value={settings.productCategory}
          onChange={(e) => onUpdate({ productCategory: e.target.value })}
          className="rounded-md px-3 py-2 text-xs text-[#171717] shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsla(212,100%,48%,1)]"
        >
          <option value="">Select category...</option>
          <option value="food_beverage">Food & Beverage</option>
          <option value="fashion">Fashion & Apparel</option>
          <option value="beauty">Beauty & Personal Care</option>
          <option value="tech">Technology & Gadgets</option>
          <option value="health">Health & Wellness</option>
          <option value="finance">Finance & Banking</option>
          <option value="travel">Travel & Tourism</option>
          <option value="education">Education & Training</option>
          <option value="real_estate">Real Estate & Property</option>
          <option value="automotive">Automotive</option>
          <option value="entertainment">Entertainment & Media</option>
          <option value="ecommerce">E-Commerce & Retail</option>
          <option value="other">Other</option>
        </select>
      </div>

      {/* Toggles */}
      <ToggleRow
        label="Compliance Check"
        description={
          settings.complianceEnabled
            ? "Ads are auto-checked against cultural guidelines"
            : "Skipped — ads show as pending compliance"
        }
        enabled={settings.complianceEnabled}
        onToggle={() => onUpdate({ complianceEnabled: !settings.complianceEnabled })}
      />

      <ToggleRow
        label="Video V2 — Multi-Scene Storyboard"
        description={
          settings.videoV2Enabled
            ? "Storyboard → keyframes → Veo clips → subtitles + transitions"
            : "Single Veo clip (V1). Enable for a rich multi-scene ad"
        }
        enabled={settings.videoV2Enabled}
        onToggle={() => onUpdate({ videoV2Enabled: !settings.videoV2Enabled })}
      />
    </div>
  );
}

// ─── Main Panel ──────────────────────────────────────────────────────────────

type Tab = "consumer" | "generation";

export function SettingsPanel({ settings, onUpdate, onClose }: SettingsPanelProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<Tab>("consumer");

  useGSAP(
    () => {
      gsap.from(".settings-card", {
        autoAlpha: 0,
        y: 12,
        scale: 0.97,
        duration: 0.35,
        ease: "power2.out",
      });
    },
    { scope: containerRef }
  );

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 z-40 flex items-center justify-center bg-[#09090b]/50 backdrop-blur-xs pointer-events-auto"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="settings-card pointer-events-auto w-full max-w-lg rounded-xl bg-white p-0 shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px,rgba(0,0,0,0.04)_0px_2px_2px,rgba(0,0,0,0.04)_0px_8px_8px_-8px,#fafafa_0px_0px_0px_1px] relative overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#ebebeb] px-6 py-4">
          <h2 className="!text-sm !font-bold text-[#171717] tracking-tight !m-0">Settings</h2>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[#666666] hover:bg-[#fafafa] hover:text-[#171717] transition-colors cursor-pointer"
            title="Close settings"
          >
            <X size={16} />
          </button>
        </div>

        {/* Tab bar */}
        <div className="px-6 pt-4 pb-2 border-b border-[#ebebeb] bg-[#fafafa]">
          <div className="flex p-1 bg-[#ebebeb]/50 rounded-lg border border-[#ebebeb]" role="tablist">
            {([
              { key: "consumer", label: "Target Consumer" },
              { key: "generation", label: "Generation Settings" },
            ] as { key: Tab; label: string }[]).map((tab) => {
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex-1 py-1.5 px-3 text-center text-xs rounded-md transition-all cursor-pointer ${
                    isActive
                      ? "bg-white text-[#171717] font-semibold shadow-sm border border-[#ebebeb]"
                      : "text-[#666666] hover:text-[#171717] font-medium"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Content */}
        <div className="max-h-[60vh] overflow-y-auto px-6 py-5">
          {activeTab === "consumer" ? (
            <TargetConsumerTab settings={settings} onUpdate={onUpdate} />
          ) : (
            <GenerationTab settings={settings} onUpdate={onUpdate} />
          )}
        </div>
      </div>
    </div>
  );
}

export default SettingsPanel;
