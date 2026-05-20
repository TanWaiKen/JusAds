export interface Campaign {
  id: string;
  title: string;
  objective: string;
  product: string;
  market: string;
  status: "Active" | "Draft" | "Review";
  insights: string[];
  references: string[];
}

export const campaignService = {
  getDefaultCampaigns(): Campaign[] {
    return [
      {
        id: "raya_2024",
        title: "Raya Gifting 2024",
        objective: "Festival Launch",
        product: "Premium Hampers",
        market: "Malaysia (MY)",
        status: "Active",
        insights: [
          "Uses local dialect humor to engage regional users.",
          "Fast-paced editing aligned with trending audio beats.",
          "ASMR-style focus on premium packaging textures."
        ],
        references: [
          "raya_unboxing_reference.mp4",
          "family_gathering_vibe.mp4",
          "hampers_aesthetic.mp4"
        ]
      },
      {
        id: "tech_summer",
        title: "Tech Summer Flash",
        objective: "Direct Response",
        product: "Smartphone X",
        market: "Thailand (TH)",
        status: "Draft",
        insights: [
          "Vibrant color contrast matching Bangkok summer aesthetics.",
          "Clear call-to-action overlays appearing in first 3 seconds.",
          "Features local micro-influencer reviews as social proof."
        ],
        references: [
          "tech_unboxing_th.mp4",
          "summer_lifestyle_vlog.mp4"
        ]
      },
      {
        id: "skin_glow",
        title: "Skin Glow 2.0",
        objective: "Brand Awareness",
        product: "Hydration Serum",
        market: "Indonesia (ID)",
        status: "Review",
        insights: [
          "Focuses on skin hydration routines in high-humidity climates.",
          "Soft-glowing skin aesthetic shots with pastel backdrops.",
          "Uses local language slang for 'dewy skin'."
        ],
        references: [
          "skincare_routine_id.mp4",
          "glow_before_after.mp4"
        ]
      }
    ];
  },

  async localizeCampaign(_campaignId: string): Promise<string[]> {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 3000));
    return [
      "Generated high-converting hooks tailored to local culture.",
      "Optimized caption overlays for immediate visual hook.",
      "Included dynamic soundtrack recommendations based on current local hits."
    ];
  }
};
