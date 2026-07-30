#!/usr/bin/env node

/**
 * Operator-run, idempotent PredictHQ -> Supabase event refresh.
 * Requires Node 20.6+ for --env-file. No credentials are logged.
 */

const API_URL = "https://api.predicthq.com/v1/events/";
const SUPABASE_TABLE = "cultural_events";
const MARKET_NAMES = { MY: "malaysia", SG: "singapore", TH: "thailand", ID: "indonesia", VN: "vietnam", PH: "philippines" };
const EVENT_TYPES = {
  sports: "sports", festivals: "festive", concerts: "festive",
  "public-holidays": "national", "school-holidays": "national", observances: "national",
};
const CATEGORY_FILTER = "festivals,sports,public-holidays,concerts,expos,conferences,observances,community";

function option(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

const dryRun = process.argv.includes("--dry-run");
const days = Math.max(1, Math.min(365, Number(option("--days", "120")) || 120));
const limit = Math.max(1, Math.min(100, Number(option("--limit", "100")) || 100));
const markets = option("--markets", "MY,SG,TH,ID,VN,PH").split(",").map((item) => item.trim().toUpperCase()).filter((item) => MARKET_NAMES[item]);
const predictKey = process.env.PREDICTHQ_API_KEY;
const supabaseUrl = (process.env.SUPABASE_URL || "").replace(/\/$/, "");
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;

if (!predictKey || !supabaseUrl || !supabaseKey) {
  console.error("Missing PREDICTHQ_API_KEY, SUPABASE_URL, or server-only SUPABASE_KEY.");
  process.exit(2);
}

const dateOnly = (date) => new Date(date).toISOString().slice(0, 10);
const now = new Date();
const end = new Date(now);
end.setUTCDate(end.getUTCDate() + days);

function normalize(event, market) {
  if (!event || !event.id) return null;
  const category = Array.isArray(event.category) ? event.category[0] : event.category;
  return {
    name: String(event.title || "Untitled event").slice(0, 500),
    market,
    start_date: dateOnly(event.start || now),
    end_date: dateOnly(event.end || event.start || now),
    event_type: EVENT_TYPES[String(category || "").toLowerCase()] || "global",
    tags: Array.isArray(event.labels) ? event.labels.filter((tag) => typeof tag === "string").slice(0, 25) : [],
    impact_score: Math.max(0, Math.min(100, Number(event.rank) || 0)),
    source: "predicthq",
    source_event_id: String(event.id),
    source_updated_at: event.updated ? new Date(event.updated).toISOString() : null,
    source_payload: event,
    last_synced_at: new Date().toISOString(),
  };
}

async function fetchEvents(countryCode) {
  const params = new URLSearchParams({
    "active.gte": dateOnly(now), "active.lte": dateOnly(end), category: CATEGORY_FILTER,
    country: countryCode, limit: String(limit), sort: "rank",
  });
  const response = await fetch(`${API_URL}?${params}`, { headers: { Authorization: `Bearer ${predictKey}`, Accept: "application/json" } });
  if (!response.ok) throw new Error(`PredictHQ returned ${response.status} for ${countryCode}`);
  const body = await response.json();
  if (body.overflow) console.warn(`PredictHQ subscription overflow for ${countryCode}; refine the query before relying on this data.`);
  return Array.isArray(body.results) ? body.results : [];
}

async function upsert(rows) {
  const response = await fetch(`${supabaseUrl}/rest/v1/${SUPABASE_TABLE}?on_conflict=source,source_event_id`, {
    method: "POST",
    headers: { apikey: supabaseKey, Authorization: `Bearer ${supabaseKey}`, "Content-Type": "application/json", Prefer: "resolution=merge-duplicates,return=representation" },
    body: JSON.stringify(rows),
  });
  if (!response.ok) throw new Error(`Supabase upsert failed: ${response.status} ${await response.text()}`);
  return response.json();
}

const allRows = [];
for (const code of markets) {
  const results = await fetchEvents(code);
  console.log(`${code}: ${results.length} PredictHQ events fetched`);
  allRows.push(...results.map((event) => normalize(event, MARKET_NAMES[code])).filter(Boolean));
}
const uniqueRows = [...new Map(allRows.map((row) => [row.source_event_id, row])).values()];
console.log(`Total: ${uniqueRows.length} unique events${dryRun ? " (dry run; no database write)" : ""}.`);
if (!dryRun && uniqueRows.length) {
  const written = await upsert(uniqueRows);
  console.log(`Supabase: ${written.length} PredictHQ rows inserted or updated.`);
}
