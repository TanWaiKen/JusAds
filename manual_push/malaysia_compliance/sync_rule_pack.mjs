#!/usr/bin/env node
/**
 * Read or apply the reviewed Malaysian rule pack with no external dependency.
 *
 * Usage:
 *   node manual_push/malaysia_compliance/sync_rule_pack.mjs --dry-run
 *   node manual_push/malaysia_compliance/sync_rule_pack.mjs --apply
 *
 * Reads the server-side Supabase credentials from backend/.env. It never logs
 * credentials. `--apply` only changes regulatory rule metadata: it does not
 * touch users, projects, media, compliance results, or migrations.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { LEGACY_MALAYSIA_RULE_IDS, MALAYSIA_RULE_PACK } from "./malaysia_rule_pack.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const envPath = path.join(root, "backend", ".env");
const mode = process.argv.includes("--apply") ? "apply" : "dry-run";

function readEnv(filename) {
  if (!fs.existsSync(filename)) throw new Error("backend/.env is required for this operator script.");
  const values = {};
  for (const rawLine of fs.readFileSync(filename, "utf8").split(/\r?\n/)) {
    const match = rawLine.match(/^\s*([^#=]+?)\s*=\s*(.*?)\s*$/);
    if (!match) continue;
    let value = match[2];
    if ((value.startsWith("\"") && value.endsWith("\"")) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    values[match[1].trim()] = value;
  }
  return values;
}

const env = readEnv(envPath);
const baseUrl = (env.SUPABASE_URL || "").replace(/\/$/, "");
const apiKey = env.SUPABASE_KEY;
if (!baseUrl || !apiKey) throw new Error("SUPABASE_URL and SUPABASE_KEY must be configured in backend/.env.");

async function request(relativePath, options = {}) {
  const response = await fetch(`${baseUrl}/rest/v1/${relativePath}`, {
    ...options,
    headers: {
      apikey: apiKey,
      Authorization: `Bearer ${apiKey}`,
      "User-Agent": "JusAds-malaysia-rule-sync/1.0",
      ...options.headers,
    },
  });
  if (!response.ok) {
    // Schema and validation errors are safe and necessary for the operator to
    // diagnose; truncate them so a proxy never produces an unbounded log.
    const detail = (await response.text()).replace(/\s+/g, " ").slice(0, 500);
    throw new Error(`Supabase request failed (${response.status}): ${detail || "no detail returned"}`);
  }
  // PostgREST can reply 200/201 with an intentionally empty body when
  // `return=minimal` is requested, not only with 204.
  const body = await response.text();
  return body ? JSON.parse(body) : null;
}

async function listActiveRules() {
  return request("ad_policy_rules?source=eq.malaysia&select=id,rule_title,framework,last_updated,evidence_urls&order=id");
}

async function apply() {
  // Upsert the reviewed active rule pack before retiring legacy rows, so there
  // is no window where active nationwide rule retrieval is empty.
  await request("ad_policy_rules?on_conflict=id", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Prefer: "resolution=merge-duplicates,return=minimal",
    },
    body: JSON.stringify(MALAYSIA_RULE_PACK),
  });

  const legacyFilter = LEGACY_MALAYSIA_RULE_IDS.map(encodeURIComponent).join(",");
  await request(`ad_policy_rules?id=in.(${legacyFilter})&source=eq.malaysia`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Prefer: "return=minimal" },
    body: JSON.stringify({ source: "malaysia_legacy_review_2026" }),
  });
}

try {
  const before = await listActiveRules();
  console.log(`Mode: ${mode}. Active nationwide Malaysia rules before sync: ${before.length}.`);
  if (mode === "apply") {
    await apply();
    const after = await listActiveRules();
    const ids = new Set(after.map((rule) => rule.id));
    const missing = MALAYSIA_RULE_PACK.filter((rule) => rule.source === "malaysia" && !ids.has(rule.id));
    if (missing.length) throw new Error(`Verification failed: ${missing.length} reviewed nationwide rule(s) are absent.`);
    const rulesWithoutEvidence = after.filter((rule) => !Array.isArray(rule.evidence_urls) || !rule.evidence_urls.length);
    if (rulesWithoutEvidence.length) throw new Error(`Verification failed: ${rulesWithoutEvidence.length} active nationwide rule(s) lack source URLs.`);
    console.log(`Applied and verified ${after.length} active nationwide Malaysia rule(s).`);
    console.log("DBKL outdoor rules are stored under source=outdoor_dbkl and are intentionally excluded from nationwide online evaluation.");
  } else {
    console.log(`Would upsert ${MALAYSIA_RULE_PACK.length} reviewed rules and retire ${LEGACY_MALAYSIA_RULE_IDS.length} legacy Malaysia rows from active evaluation.`);
  }
} catch (error) {
  console.error(`Rule-pack sync failed: ${error instanceof Error ? error.message : "unknown error"}`);
  process.exitCode = 1;
}
