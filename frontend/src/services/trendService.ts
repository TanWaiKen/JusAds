export interface TrendSignal {
  id: string;
  title: string;
  category: "Foot Traffic" | "Social Buzz";
  description: string;
  whoCares: string;
  impact: string;
  riskLevel: "Low" | "Medium" | "High";
  riskDescription: string;
  percentage: number;
}

export const trendService = {
  getDefaultSignals(): TrendSignal[] {
    return [
      {
        id: "mosquito_jakarta",
        title: "Mosquito Traps in Central Jakarta",
        category: "Foot Traffic",
        description: "Foot traffic at home supply stores in Jakarta is up 18% following recent rain forecasts.",
        whoCares: "Families with children living in central residential areas.",
        impact: "Higher conversion for localized 'Protection for Kids' ads in this district.",
        riskLevel: "Low",
        riskDescription: "No sensitive cultural or political associations.",
        percentage: 18
      },
      {
        id: "ramadan_kl",
        title: "Ramadan Midnight Shopping Peaks",
        category: "Foot Traffic",
        description: "Surge in mall visits between 10PM and 1AM across Kuala Lumpur malls.",
        whoCares: "Young professionals looking for post-Iftar gatherings and fashion deals.",
        impact: "Scheduled push notifications for 9PM will see 2x engagement.",
        riskLevel: "Medium",
        riskDescription: "Ensure respectful tone regarding religious observance times.",
        percentage: 45
      },
      {
        id: "raya_gifts",
        title: "Raya Gifting Bundles queries",
        category: "Social Buzz",
        description: "'Personalized hamper' and 'Gifting bundles' searches grew 40% this week.",
        whoCares: "SME owners and corporate HR departments planning employee gifts.",
        impact: "Opportunity for B2B targeting with 'Hassle-free gifting' hooks.",
        riskLevel: "Low",
        riskDescription: "Standard holiday commercial trend. No issues.",
        percentage: 40
      },
      {
        id: "sg_bag_debate",
        title: "Local Policy Debate in SG",
        category: "Social Buzz",
        description: "Viral TikTok debate regarding new plastic bag charges at supermarkets.",
        whoCares: "Eco-conscious consumers and bargain hunters in Singapore.",
        impact: "High engagement potential but high risk of brand backlash.",
        riskLevel: "High",
        riskDescription: "Sensitive social policy. Framing can be easily misconstrued as political.",
        percentage: 72
      }
    ];
  }
};
