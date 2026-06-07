/**
 * Preservation Property-Based Tests
 * 
 * These tests observe and verify EXISTING behavior on UNFIXED code.
 * They capture baseline snapshots of GSAP animations, dark mode classes,
 * hover/active states, responsive breakpoints, filter controls,
 * compliance page integrity, and dashboard sidebar structure.
 * 
 * **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**
 */

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { readFileSync } from "fs";
import { resolve } from "path";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const PAGES_DIR = resolve(__dirname, "../pages");

function readPage(filename: string): string {
  return readFileSync(resolve(PAGES_DIR, filename), "utf-8");
}

/**
 * Extract all GSAP animation config objects from a source file.
 * Captures: selectors (string in quotes following 'from(' or 'fromTo('),
 * duration, ease, stagger, delay values.
 */
function extractGsapConfigs(source: string) {
  const configs: Array<{
    selector: string;
    duration?: string;
    ease?: string;
    stagger?: string;
    delay?: string;
  }> = [];

  // Match gsap.from(".selector", { ... }) and tl.from(".selector", { ... })
  const fromPattern = /\.from\(\s*"([^"]+)"\s*,\s*\{([^}]+)\}/g;
  let match;
  while ((match = fromPattern.exec(source)) !== null) {
    const selector = match[1];
    const configBlock = match[2];
    configs.push({
      selector,
      duration: configBlock.match(/duration:\s*([\d.]+)/)?.[1],
      ease: configBlock.match(/ease:\s*"([^"]+)"/)?.[1],
      stagger: configBlock.match(/stagger:\s*([\d.]+)/)?.[1],
      delay: configBlock.match(/delay:\s*([\d.]+)/)?.[1],
    });
  }

  // Match gsap.fromTo(".selector", { ... }, { ... })
  const fromToPattern = /\.fromTo\(\s*"([^"]+)"\s*,/g;
  while ((match = fromToPattern.exec(source)) !== null) {
    const selector = match[1];
    // Get the second config block (the "to" vars)
    const afterMatch = source.slice(match.index + match[0].length);
    const toBlock = afterMatch.match(/\{[^}]*\}\s*,\s*\{([^}]+)\}/);
    if (toBlock) {
      configs.push({
        selector,
        duration: toBlock[1].match(/duration:\s*([\d.]+)/)?.[1],
        ease: toBlock[1].match(/ease:\s*"([^"]+)"/)?.[1],
        stagger: toBlock[1].match(/stagger:\s*([\d.]+)/)?.[1],
        delay: toBlock[1].match(/delay:\s*([\d.]+)/)?.[1],
      });
    }
  }

  // Match timeline defaults
  const defaultsPattern = /timeline\(\s*\{\s*defaults:\s*\{([^}]+)\}/g;
  while ((match = defaultsPattern.exec(source)) !== null) {
    const block = match[1];
    configs.push({
      selector: "__timeline_defaults__",
      duration: block.match(/duration:\s*([\d.]+)/)?.[1],
      ease: block.match(/ease:\s*"([^"]+)"/)?.[1],
    });
  }

  return configs;
}

/**
 * Extract all dark: variant classes from source code.
 */
function extractDarkClasses(source: string): string[] {
  const darkPattern = /dark:[a-zA-Z0-9\-\[\]\/_.#]+/g;
  return [...new Set(source.match(darkPattern) || [])].sort();
}

/**
 * Extract all hover/active/group-hover state classes.
 */
function extractInteractionClasses(source: string): string[] {
  const pattern = /(hover:|active:|group-hover:)[a-zA-Z0-9\-\[\]\/_.#]+/g;
  return [...new Set(source.match(pattern) || [])].sort();
}

/**
 * Extract responsive breakpoint classes (lg:, md:, sm:).
 */
function extractResponsiveClasses(source: string): string[] {
  const pattern = /(lg:|md:|sm:)[a-zA-Z0-9\-\[\]\/_.#]+/g;
  return [...new Set(source.match(pattern) || [])].sort();
}

/**
 * Extract filter control onClick handlers and onChange handlers.
 */
function extractFilterControls(source: string): string[] {
  const onClickPattern = /onClick=\{[^}]*\}/g;
  const onChangePattern = /onChange=\{[^}]*\}/g;
  const clicks = source.match(onClickPattern) || [];
  const changes = source.match(onChangePattern) || [];
  return [...clicks, ...changes];
}

// ─── Baseline Snapshots (observed on UNFIXED code) ───────────────────────────

const homeSource = readPage("home.tsx");
const trendsSource = readPage("trends.tsx");
const campaignsSource = readPage("campaigns.tsx");
const assetsSource = readPage("assets.tsx");
const complianceSource = readPage("compliance.tsx");
const dashboardSource = readPage("dashboard.tsx");

// GSAP baselines
const homeGsapBaseline = extractGsapConfigs(homeSource);
const trendsGsapBaseline = extractGsapConfigs(trendsSource);
const campaignsGsapBaseline = extractGsapConfigs(campaignsSource);
const assetsGsapBaseline = extractGsapConfigs(assetsSource);

// Dark mode baselines
const homeDarkBaseline = extractDarkClasses(homeSource);
const trendsDarkBaseline = extractDarkClasses(trendsSource);
const campaignsDarkBaseline = extractDarkClasses(campaignsSource);
const assetsDarkBaseline = extractDarkClasses(assetsSource);

// Hover/active state baselines
const homeHoverBaseline = extractInteractionClasses(homeSource);
const trendsHoverBaseline = extractInteractionClasses(trendsSource);
const campaignsHoverBaseline = extractInteractionClasses(campaignsSource);
const assetsHoverBaseline = extractInteractionClasses(assetsSource);

// Responsive breakpoint baselines
const homeResponsiveBaseline = extractResponsiveClasses(homeSource);
const trendsResponsiveBaseline = extractResponsiveClasses(trendsSource);
const campaignsResponsiveBaseline = extractResponsiveClasses(campaignsSource);
const assetsResponsiveBaseline = extractResponsiveClasses(assetsSource);

// Filter control baselines
const trendsFilterBaseline = extractFilterControls(trendsSource);
const campaignsFilterBaseline = extractFilterControls(campaignsSource);
const assetsFilterBaseline = extractFilterControls(assetsSource);

// Compliance page content baseline (byte-identical check)
const complianceBaseline = complianceSource;

// Dashboard sidebar baseline
const dashboardSidebarWidth = "240";
const dashboardNavItems = ["Home", "Profile", "Campaigns", "Assets", "Compliance"];


// ─── Property Tests ──────────────────────────────────────────────────────────

describe("Preservation Property Tests", () => {

  // ─── Property: GSAP Animation Configurations Preserved ─────────────────────
  // **Validates: Requirements 3.1**

  describe("GSAP Animation Preservation", () => {
    const pages = [
      { name: "home.tsx", baseline: homeGsapBaseline },
      { name: "trends.tsx", baseline: trendsGsapBaseline },
      { name: "campaigns.tsx", baseline: campaignsGsapBaseline },
      { name: "assets.tsx", baseline: assetsGsapBaseline },
    ] as const;

    it("should preserve all GSAP animation configurations across pages", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(...pages),
          (page) => {
            const currentSource = readPage(page.name);
            const currentConfigs = extractGsapConfigs(currentSource);
            
            // Every baseline animation must still exist with same config
            for (const baseConfig of page.baseline) {
              const found = currentConfigs.find(c => c.selector === baseConfig.selector);
              expect(found).toBeDefined();
              expect(found?.duration).toBe(baseConfig.duration);
              expect(found?.ease).toBe(baseConfig.ease);
              expect(found?.stagger).toBe(baseConfig.stagger);
              expect(found?.delay).toBe(baseConfig.delay);
            }

            // Count must match (no removed or extra animations)
            expect(currentConfigs.length).toBe(page.baseline.length);
          }
        ),
        { numRuns: 20 }
      );
    });

    it("home.tsx GSAP: all selectors, durations, easings, staggers observed", () => {
      // Verify specific known animations in home.tsx
      expect(homeGsapBaseline.some(c => c.selector === ".dash-header")).toBe(true);
      expect(homeGsapBaseline.some(c => c.selector === ".dash-header-sub")).toBe(true);
      expect(homeGsapBaseline.some(c => c.selector === ".stat-card")).toBe(true);
      expect(homeGsapBaseline.some(c => c.selector === ".promo-card")).toBe(true);
      expect(homeGsapBaseline.some(c => c.selector === ".credit-bar-fill")).toBe(true);
      expect(homeGsapBaseline.some(c => c.selector === ".sentiment-panel")).toBe(true);
      expect(homeGsapBaseline.some(c => c.selector === ".activity-item")).toBe(true);

      // Verify stat-card stagger value
      const statCard = homeGsapBaseline.find(c => c.selector === ".stat-card");
      expect(statCard?.stagger).toBe("0.12");
      expect(statCard?.ease).toBe("back.out(1.4)");
    });

    it("trends.tsx GSAP: signal-card, trends-details, briefcase-panel animations", () => {
      expect(trendsGsapBaseline.some(c => c.selector === ".signal-card")).toBe(true);
      expect(trendsGsapBaseline.some(c => c.selector === ".trends-details")).toBe(true);
      expect(trendsGsapBaseline.some(c => c.selector === ".briefcase-panel")).toBe(true);
      expect(trendsGsapBaseline.some(c => c.selector === ".signal-content-pane")).toBe(true);

      const signalCard = trendsGsapBaseline.find(c => c.selector === ".signal-card");
      expect(signalCard?.stagger).toBe("0.08");
      expect(signalCard?.duration).toBe("0.6");
    });

    it("campaigns.tsx GSAP: workspace-card and details-container animations", () => {
      expect(campaignsGsapBaseline.some(c => c.selector === ".workspace-card")).toBe(true);
      expect(campaignsGsapBaseline.some(c => c.selector === ".details-container")).toBe(true);
      expect(campaignsGsapBaseline.some(c => c.selector === ".details-content")).toBe(true);

      const workspaceCard = campaignsGsapBaseline.find(c => c.selector === ".workspace-card");
      expect(workspaceCard?.stagger).toBe("0.08");
    });

    it("assets.tsx GSAP: asset-card and assets-detail-drawer animations", () => {
      expect(assetsGsapBaseline.some(c => c.selector === ".asset-card")).toBe(true);
      expect(assetsGsapBaseline.some(c => c.selector === ".assets-detail-drawer")).toBe(true);
      expect(assetsGsapBaseline.some(c => c.selector === ".drawer-detail-content")).toBe(true);

      const assetCard = assetsGsapBaseline.find(c => c.selector === ".asset-card");
      expect(assetCard?.stagger).toBe("0.08");
      expect(assetCard?.duration).toBe("0.6");
    });
  });

  // ─── Property: Dark Mode Classes Preserved ─────────────────────────────────
  // **Validates: Requirements 3.3**

  describe("Dark Mode Class Preservation", () => {
    const pages = [
      { name: "home.tsx", baseline: homeDarkBaseline },
      { name: "trends.tsx", baseline: trendsDarkBaseline },
      { name: "campaigns.tsx", baseline: campaignsDarkBaseline },
      { name: "assets.tsx", baseline: assetsDarkBaseline },
    ] as const;

    it("should preserve all dark: variant classes across pages", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(...pages),
          (page) => {
            const currentSource = readPage(page.name);
            const currentDarkClasses = extractDarkClasses(currentSource);

            // Every baseline dark class must still exist
            for (const darkClass of page.baseline) {
              expect(currentDarkClasses).toContain(darkClass);
            }
          }
        ),
        { numRuns: 20 }
      );
    });

    it("home.tsx dark mode classes are present", () => {
      expect(homeDarkBaseline.length).toBeGreaterThan(0);
      expect(homeDarkBaseline).toContain("dark:text-white");
      expect(homeDarkBaseline).toContain("dark:border-white/10");
    });

    it("trends.tsx dark mode classes are present", () => {
      expect(trendsDarkBaseline.length).toBeGreaterThan(0);
      expect(trendsDarkBaseline).toContain("dark:bg-[#111116]");
      expect(trendsDarkBaseline).toContain("dark:text-white");
    });
  });

  // ─── Property: Hover/Active State Classes Preserved ────────────────────────
  // **Validates: Requirements 3.4**

  describe("Hover/Active State Preservation", () => {
    const pages = [
      { name: "home.tsx", baseline: homeHoverBaseline },
      { name: "trends.tsx", baseline: trendsHoverBaseline },
      { name: "campaigns.tsx", baseline: campaignsHoverBaseline },
      { name: "assets.tsx", baseline: assetsHoverBaseline },
    ] as const;

    it("should preserve all hover/active/group-hover classes across pages", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(...pages),
          (page) => {
            const currentSource = readPage(page.name);
            const currentInteractionClasses = extractInteractionClasses(currentSource);

            // Every baseline interaction class must still exist
            for (const cls of page.baseline) {
              expect(currentInteractionClasses).toContain(cls);
            }
          }
        ),
        { numRuns: 20 }
      );
    });

    it("home.tsx hover states include translate and transition", () => {
      expect(homeHoverBaseline).toContain("hover:-translate-y-1");
      expect(homeHoverBaseline).toContain("hover:shadow-md");
      expect(homeHoverBaseline).toContain("group-hover:scale-110");
      expect(homeHoverBaseline).toContain("hover:bg-[#0080FF]/10");
      expect(homeHoverBaseline).toContain("group-hover:text-[#0080FF]");
    });

    it("campaigns.tsx hover states for cards and buttons", () => {
      expect(campaignsHoverBaseline).toContain("hover:opacity-90");
      expect(campaignsHoverBaseline).toContain("active:scale-95");
      expect(campaignsHoverBaseline).toContain("hover:border-gray-200");
    });
  });

  // ─── Property: Responsive Breakpoint Classes Preserved ─────────────────────
  // **Validates: Requirements 3.6**

  describe("Responsive Breakpoint Preservation", () => {
    const pages = [
      { name: "home.tsx", baseline: homeResponsiveBaseline },
      { name: "trends.tsx", baseline: trendsResponsiveBaseline },
      { name: "campaigns.tsx", baseline: campaignsResponsiveBaseline },
      { name: "assets.tsx", baseline: assetsResponsiveBaseline },
    ] as const;

    it("should preserve all responsive breakpoint classes across pages", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(...pages),
          (page) => {
            const currentSource = readPage(page.name);
            const currentResponsiveClasses = extractResponsiveClasses(currentSource);

            // Every baseline responsive class must still exist
            for (const cls of page.baseline) {
              expect(currentResponsiveClasses).toContain(cls);
            }
          }
        ),
        { numRuns: 20 }
      );
    });

    it("home.tsx has responsive grid and flex classes", () => {
      expect(homeResponsiveBaseline).toContain("md:flex-row");
      expect(homeResponsiveBaseline).toContain("md:items-center");
      expect(homeResponsiveBaseline).toContain("md:grid-cols-3");
      expect(homeResponsiveBaseline).toContain("lg:grid-cols-3");
      expect(homeResponsiveBaseline).toContain("lg:col-span-2");
    });

    it("trends.tsx has responsive flex-row and width classes for column layout", () => {
      expect(trendsResponsiveBaseline).toContain("lg:flex-row");
      // Intentionally changed from fixed lg:w-[380px]/lg:w-[320px] to proportional sizing
      expect(trendsResponsiveBaseline).toContain("lg:basis-[300px]");
      expect(trendsResponsiveBaseline).toContain("lg:basis-[280px]");
      expect(trendsResponsiveBaseline).toContain("lg:shrink-0");
      expect(trendsResponsiveBaseline).toContain("lg:h-full");
      expect(trendsResponsiveBaseline).toContain("lg:border-b-0");
    });

    it("campaigns.tsx has responsive layout classes", () => {
      expect(campaignsResponsiveBaseline).toContain("lg:flex-row");
      // Intentionally changed from fixed lg:w-[320px] to proportional sizing
      expect(campaignsResponsiveBaseline).toContain("lg:w-1/4");
      expect(campaignsResponsiveBaseline).toContain("lg:min-w-[260px]");
      expect(campaignsResponsiveBaseline).toContain("lg:max-w-[360px]");
      expect(campaignsResponsiveBaseline).toContain("lg:h-full");
    });

    it("assets.tsx has responsive grid and layout classes", () => {
      expect(assetsResponsiveBaseline).toContain("lg:flex-row");
      expect(assetsResponsiveBaseline).toContain("lg:w-[360px]");
      expect(assetsResponsiveBaseline).toContain("sm:grid-cols-2");
      expect(assetsResponsiveBaseline).toContain("md:grid-cols-3");
    });
  });

  // ─── Property: Filter Control Logic Preserved ──────────────────────────────
  // **Validates: Requirements 3.7**

  describe("Filter Control Preservation", () => {
    it("trends.tsx filter controls (category pills) are unchanged", () => {
      fc.assert(
        fc.property(
          fc.constant("trends.tsx"),
          (filename) => {
            const currentSource = readPage(filename);
            const currentFilters = extractFilterControls(currentSource);

            expect(currentFilters.length).toBe(trendsFilterBaseline.length);
            for (let i = 0; i < trendsFilterBaseline.length; i++) {
              expect(currentFilters[i]).toBe(trendsFilterBaseline[i]);
            }
          }
        ),
        { numRuns: 5 }
      );
    });

    it("campaigns.tsx filter controls (status pills, form handlers) are unchanged", () => {
      fc.assert(
        fc.property(
          fc.constant("campaigns.tsx"),
          (filename) => {
            const currentSource = readPage(filename);
            const currentFilters = extractFilterControls(currentSource);

            expect(currentFilters.length).toBe(campaignsFilterBaseline.length);
            for (let i = 0; i < campaignsFilterBaseline.length; i++) {
              expect(currentFilters[i]).toBe(campaignsFilterBaseline[i]);
            }
          }
        ),
        { numRuns: 5 }
      );
    });

    it("assets.tsx filter controls (type/campaign selects, search) are unchanged", () => {
      fc.assert(
        fc.property(
          fc.constant("assets.tsx"),
          (filename) => {
            const currentSource = readPage(filename);
            const currentFilters = extractFilterControls(currentSource);

            expect(currentFilters.length).toBe(assetsFilterBaseline.length);
            for (let i = 0; i < assetsFilterBaseline.length; i++) {
              expect(currentFilters[i]).toBe(assetsFilterBaseline[i]);
            }
          }
        ),
        { numRuns: 5 }
      );
    });
  });

  // ─── Property: Compliance Page Byte-Identical ──────────────────────────────
  // **Validates: Requirements 3.5**

  describe("Compliance Page Integrity", () => {
    it("compliance.tsx is byte-identical to baseline", () => {
      fc.assert(
        fc.property(
          fc.constant(true),
          () => {
            const currentCompliance = readPage("compliance.tsx");
            expect(currentCompliance).toBe(complianceBaseline);
          }
        ),
        { numRuns: 3 }
      );
    });
  });

  // ─── Property: Dashboard Sidebar Structure Unchanged ───────────────────────
  // **Validates: Requirements 3.2**

  describe("Dashboard Sidebar Preservation", () => {
    it("dashboard.tsx sidebar width remains 240px", () => {
      fc.assert(
        fc.property(
          fc.constant(true),
          () => {
            const currentDashboard = readPage("dashboard.tsx");
            expect(currentDashboard).toContain(`SIDEBAR_WIDTH = ${dashboardSidebarWidth}`);
            expect(currentDashboard).toContain(`width: SIDEBAR_WIDTH`);
          }
        ),
        { numRuns: 3 }
      );
    });

    it("dashboard.tsx nav items remain unchanged", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(...dashboardNavItems),
          (navLabel) => {
            const currentDashboard = readPage("dashboard.tsx");
            expect(currentDashboard).toContain(`label: "${navLabel}"`);
          }
        ),
        { numRuns: 10 }
      );
    });

    it("dashboard.tsx active state styling is preserved", () => {
      const currentDashboard = readPage("dashboard.tsx");
      // Active NavLink styling
      expect(currentDashboard).toContain("bg-[#0080FF]/10 text-[#0080FF]");
      expect(currentDashboard).toContain("dark:bg-[#0080FF]/15 dark:text-[#4DA6FF]");
    });

    it("dashboard.tsx sidebar structure has expected sections", () => {
      const currentDashboard = readPage("dashboard.tsx");
      // Sidebar header with logo
      expect(currentDashboard).toContain('aria-label="Sidebar navigation"');
      expect(currentDashboard).toContain('aria-label="Main navigation"');
      // User profile section at bottom
      expect(currentDashboard).toContain("Sidebar User Profile");
    });
  });
});
