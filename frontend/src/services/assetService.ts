export interface CreativeAsset {
  id: string;
  title: string;
  campaign: string;
  description: string;
  created: string;
  format: string;
  size: string;
  resolution: string;
  tags: string[];
  compliance: string;
  gradient: string;
}

export const assetService = {
  getDefaultAssets(): CreativeAsset[] {
    return [
      {
        id: "aria_summer",
        title: "Aria Summer V1",
        campaign: "Summer Collection 2024",
        description: "High energy, vibrant tone.",
        created: "Oct 24, 2024",
        format: "MP4 (9:16)",
        size: "12.4 MB",
        resolution: "1080 x 1920",
        tags: ["High Energy", "Vibrant", "Modern"],
        compliance: "Creative meets all brand safety requirements for global distribution. Text-to-image ratio is within limits (14%). Contrast levels pass WCAG AA standards for accessibility.",
        gradient: "from-amber-400 via-pink-500 to-indigo-600"
      },
      {
        id: "velocity_motion",
        title: "Velocity Motion 04",
        campaign: "Q3 Global Outreach",
        description: "Focus on rapid movement.",
        created: "Oct 22, 2024",
        format: "MP4 (16:9)",
        size: "8.1 MB",
        resolution: "1920 x 1080",
        tags: ["Dynamic", "Fast-Paced"],
        gradient: "from-blue-600 via-cyan-400 to-indigo-500",
        compliance: "Passed AI motion comfort check. Contrast index meets standards."
      },
      {
        id: "zenith_branding",
        title: "Zenith Branding B",
        campaign: "Brand Refresh",
        description: "Minimalist, premium feel.",
        created: "Oct 20, 2024",
        format: "MOV (1:1)",
        size: "18.2 MB",
        resolution: "1080 x 1080",
        tags: ["Minimalist", "Premium", "Sleek"],
        gradient: "from-[#7B2FBE] via-[#FF6B9D] to-[#00D4AA]",
        compliance: "Meets premium branding criteria. Brand logo contrast is optimal."
      },
      {
        id: "office_lifestyle",
        title: "Office Lifestyle 12",
        campaign: "Recruitment 24",
        description: "Modern work-life balance.",
        created: "Oct 18, 2024",
        format: "MP4 (9:16)",
        size: "10.5 MB",
        resolution: "1080 x 1920",
        tags: ["Authentic", "Workplace"],
        gradient: "from-emerald-400 to-teal-700",
        compliance: "Passed human-centric asset guidelines. Neutral overlays."
      },
      {
        id: "gen_abstract",
        title: "Gen-Abstract 09",
        campaign: "Developer Portal",
        description: "Futuristic tech pattern.",
        created: "Oct 15, 2024",
        format: "MP4 (16:9)",
        size: "6.7 MB",
        resolution: "1920 x 1080",
        tags: ["Futuristic", "Tech"],
        gradient: "from-violet-600 via-purple-500 to-fuchsia-500",
        compliance: "High-contrast technical typography passes legibility audits."
      },
      {
        id: "nexus_hardware",
        title: "Nexus Hardware",
        campaign: "Hardware Launch",
        description: "Crisp, technical clarity.",
        created: "Oct 12, 2024",
        format: "MP4 (16:9)",
        size: "9.3 MB",
        resolution: "1920 x 1080",
        tags: ["Hardware", "Technical", "Clear"],
        gradient: "from-gray-700 to-slate-900",
        compliance: "Product logo dimensions are accurately framed. Hardware presentation complies with visual standards."
      }
    ];
  }
};
