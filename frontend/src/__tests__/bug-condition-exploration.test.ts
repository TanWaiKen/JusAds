/**
 * Bug Condition Exploration Property Test
 *
 * This test scans the dashboard page source files for sub-minimum typography,
 * truncation, spacing, and fixed-width panel violations that contradict the
 * design token system.
 *
 * **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8**
 *
 * EXPECTED: This test MUST FAIL on unfixed code — failure confirms the bug exists.
 */

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import * as fs from "node:fs";
import * as path from "node:path";

// Page files to scan
const PAGE_FILES = ["home.tsx", "trends.tsx", "assets.tsx"];
const PAGES_DIR = path.resolve(__dirname, "../pages");

// Read all page sources once
function readPageSource(filename: string): string {
  return fs.readFileSync(path.join(PAGES_DIR, filename), "utf-8");
}

// Sub-minimum typography patterns (for non-monospace UI text)
const SUB_MINIMUM_TYPOGRAPHY_PATTERNS = [
  /text-\[10px\]/g,
  /text-\[12px\]/g,
  /text-\[9px\]/g,
  /text-\[12\.5px\]/g,
];

// Truncation + max-width restriction pattern
const TRUNCATE_MAX_WIDTH_PATTERN = /truncate\s+max-w-\[170px\]|max-w-\[170px\]\s+truncate/g;

// Line-clamp on primary content
const LINE_CLAMP_PATTERN = /line-clamp-2/g;

// Sub-minimum spacing patterns
const SUB_MINIMUM_SPACING_PATTERNS = [
  /gap-0\.5/g,
  /space-y-0\.5/g,
  /mt-0\.5/g,
];

// Fixed-width panel patterns
const FIXED_WIDTH_PANEL_PATTERNS = [
  /w-\[380px\]/g,
  /w-\[320px\]/g,
];

interface Violation {
  file: string;
  line: number;
  pattern: string;
  content: string;
}

function findViolations(
  source: string,
  filename: string,
  pattern: RegExp,
): Violation[] {
  const violations: Violation[] = [];
  const lines = source.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // Reset regex lastIndex for global patterns
    const regex = new RegExp(pattern.source, pattern.flags);
    let match;
    while ((match = regex.exec(line)) !== null) {
      violations.push({
        file: filename,
        line: i + 1,
        pattern: match[0],
        content: line.trim(),
      });
    }
  }

  return violations;
}

describe("Bug Condition Exploration: Sub-Minimum Typography, Truncation, Spacing, and Fixed-Width Violations", () => {
  // Load all page sources
  const pageSources = PAGE_FILES.map((file) => ({
    filename: file,
    source: readPageSource(file),
  }));

  it("Property 1: No sub-minimum typography (text-[10px], text-[12px], text-[9px], text-[12.5px]) in dashboard pages", () => {
    /**
     * **Validates: Requirements 1.1, 1.6, 1.7, 1.8**
     *
     * For any page file selected from the dashboard pages,
     * there should be NO occurrence of hardcoded sub-minimum text sizes
     * for non-monospace UI text.
     */
    fc.assert(
      fc.property(
        fc.constantFrom(...pageSources),
        ({ filename, source }) => {
          const allViolations: Violation[] = [];

          for (const pattern of SUB_MINIMUM_TYPOGRAPHY_PATTERNS) {
            const violations = findViolations(source, filename, pattern);
            allViolations.push(...violations);
          }

          if (allViolations.length > 0) {
            const summary = allViolations
              .map((v) => `  ${v.file}:${v.line} — "${v.pattern}" in: ${v.content}`)
              .join("\n");
            expect.fail(
              `Found ${allViolations.length} sub-minimum typography violation(s) in ${filename}:\n${summary}`
            );
          }
        }
      ),
      { numRuns: PAGE_FILES.length * 5 } // Run enough times to cover all pages
    );
  });

  it("Property 2: No restrictive truncation (truncate + max-w-[170px]) in dashboard pages", () => {
    /**
     * **Validates: Requirements 1.2**
     *
     * For any page file, there should be NO occurrence of truncate combined
     * with max-w-[170px] which cuts off meaningful title text.
     */
    fc.assert(
      fc.property(
        fc.constantFrom(...pageSources),
        ({ filename, source }) => {
          const violations = findViolations(source, filename, TRUNCATE_MAX_WIDTH_PATTERN);

          if (violations.length > 0) {
            const summary = violations
              .map((v) => `  ${v.file}:${v.line} — "${v.pattern}" in: ${v.content}`)
              .join("\n");
            expect.fail(
              `Found ${violations.length} restrictive truncation violation(s) in ${filename}:\n${summary}`
            );
          }
        }
      ),
      { numRuns: PAGE_FILES.length * 5 }
    );
  });

  it("Property 3: No line-clamp-2 on primary content descriptions in dashboard pages", () => {
    /**
     * **Validates: Requirements 1.3**
     *
     * For any page file, there should be NO occurrence of line-clamp-2
     * on primary content descriptions.
     */
    fc.assert(
      fc.property(
        fc.constantFrom(...pageSources),
        ({ filename, source }) => {
          const violations = findViolations(source, filename, LINE_CLAMP_PATTERN);

          if (violations.length > 0) {
            const summary = violations
              .map((v) => `  ${v.file}:${v.line} — "${v.pattern}" in: ${v.content}`)
              .join("\n");
            expect.fail(
              `Found ${violations.length} line-clamp-2 violation(s) in ${filename}:\n${summary}`
            );
          }
        }
      ),
      { numRuns: PAGE_FILES.length * 5 }
    );
  });

  it("Property 4: No sub-minimum spacing (gap-0.5, space-y-0.5, mt-0.5) in dashboard pages", () => {
    /**
     * **Validates: Requirements 1.4**
     *
     * For any page file, there should be NO occurrence of sub-minimum spacing
     * that creates a cramped, unprofessional appearance.
     */
    fc.assert(
      fc.property(
        fc.constantFrom(...pageSources),
        ({ filename, source }) => {
          const allViolations: Violation[] = [];

          for (const pattern of SUB_MINIMUM_SPACING_PATTERNS) {
            const violations = findViolations(source, filename, pattern);
            allViolations.push(...violations);
          }

          if (allViolations.length > 0) {
            const summary = allViolations
              .map((v) => `  ${v.file}:${v.line} — "${v.pattern}" in: ${v.content}`)
              .join("\n");
            expect.fail(
              `Found ${allViolations.length} sub-minimum spacing violation(s) in ${filename}:\n${summary}`
            );
          }
        }
      ),
      { numRuns: PAGE_FILES.length * 5 }
    );
  });

  it("Property 5: No fixed-width panel classes (w-[380px], w-[320px]) in dashboard pages", () => {
    /**
     * **Validates: Requirements 1.5**
     *
     * For any page file, there should be NO occurrence of fixed-width panel
     * classes that squeeze the center reading column.
     */
    fc.assert(
      fc.property(
        fc.constantFrom(...pageSources),
        ({ filename, source }) => {
          const allViolations: Violation[] = [];

          for (const pattern of FIXED_WIDTH_PANEL_PATTERNS) {
            const violations = findViolations(source, filename, pattern);
            allViolations.push(...violations);
          }

          if (allViolations.length > 0) {
            const summary = allViolations
              .map((v) => `  ${v.file}:${v.line} — "${v.pattern}" in: ${v.content}`)
              .join("\n");
            expect.fail(
              `Found ${allViolations.length} fixed-width panel violation(s) in ${filename}:\n${summary}`
            );
          }
        }
      ),
      { numRuns: PAGE_FILES.length * 5 }
    );
  });
});
