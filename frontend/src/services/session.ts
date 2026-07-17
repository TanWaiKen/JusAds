/**
 * session.ts — Typed sessionStorage helpers for passing data across navigations.
 *
 * Used by "Try Now" (Prompt Library → Canvas) and mode switching flows.
 * Data lives only in the current browser tab and auto-clears on tab close.
 */

// ─── Keys ────────────────────────────────────────────────────────────────────

const PREFILL_KEY = "jusads_prefill";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface PrefillData {
  /** The prompt text to populate in the chatbot input */
  prompt: string;
  /** Optional reference image URL to attach */
  referenceImageUrl?: string;
  /** Optional human-readable label for the reference image */
  referenceImageLabel?: string;
}

// ─── Write ───────────────────────────────────────────────────────────────────

/** Store prefill data in sessionStorage. Overwrites any existing entry. */
export function setPrefill(data: PrefillData): void {
  try {
    sessionStorage.setItem(PREFILL_KEY, JSON.stringify(data));
  } catch {
    // sessionStorage unavailable (e.g. private browsing quota exceeded) — silently fail
  }
}

// ─── Read ────────────────────────────────────────────────────────────────────

/** Read and **consume** (delete) prefill data from sessionStorage. Returns null if none. */
export function consumePrefill(): PrefillData | null {
  try {
    const raw = sessionStorage.getItem(PREFILL_KEY);
    if (!raw) return null;
    sessionStorage.removeItem(PREFILL_KEY);
    return JSON.parse(raw) as PrefillData;
  } catch {
    return null;
  }
}

/** Peek at prefill data without consuming it. */
export function peekPrefill(): PrefillData | null {
  try {
    const raw = sessionStorage.getItem(PREFILL_KEY);
    return raw ? (JSON.parse(raw) as PrefillData) : null;
  } catch {
    return null;
  }
}

// ─── Clear ───────────────────────────────────────────────────────────────────

/** Explicitly clear prefill data. */
export function clearPrefill(): void {
  try {
    sessionStorage.removeItem(PREFILL_KEY);
  } catch {
    // noop
  }
}
