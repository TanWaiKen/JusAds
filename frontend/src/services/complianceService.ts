export interface ComplianceIssue {
  type: string;
  description: string;
  original: string;
  suggested: string;
}

export interface ComplianceQueueItem {
  id: string;
  title: string;
  file: string;
  status: "Needing Attention" | "Ready to Publish" | "Checks Pending";
  issues: ComplianceIssue[];
}

export const complianceService = {
  getDefaultQueue(): ComplianceQueueItem[] {
    return [
      {
        id: "ramadan_promo",
        title: "Ramadan Promo 2024",
        file: "hero_video_v2.mp4",
        status: "Needing Attention",
        issues: [
          {
            type: "MCMC Content Code Violation",
            description: "Avoid using religious symbols or icons for commercial product promotions per Malaysia's MCMC guidelines.",
            original: "Visual elements resembling protected iconography.",
            suggested: "Replace background artwork with neutral festive patterns."
          },
          {
            type: "Accessibility Contrast Issue",
            description: "The AI detected low-contrast text overlays on skin tones which may violate readability standards.",
            original: "Low-contrast text overlays on skin tones.",
            suggested: "Increase text contrast ratio to 4.5:1 with backdrop."
          }
        ]
      },
      {
        id: "kl_opening",
        title: "KL Flagship Store Opening",
        file: "static_display_01.jpg",
        status: "Checks Pending",
        issues: [
          {
            type: "Language Localization Hook",
            description: "Contains highly localized slang that might trigger generic content warnings.",
            original: "Jom lepak tagline verification.",
            suggested: "Approve tag as standard conversational Malay dialect."
          }
        ]
      },
      {
        id: "eco_living",
        title: "Eco-Living Range",
        file: "kitchen_vibe.jpg",
        status: "Ready to Publish",
        issues: []
      }
    ];
  },

  async applyAutoFix(_itemId: string): Promise<void> {
    // Simulate auto-fix computation delay
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
};
