# Persona Research Skill
**Universal Cultural Persona Builder — Any Nation, Any Ethnicity, Any Age Group**

This skill instructs an AI agent to autonomously research, build, and deliver a structured persona JSON for any target nation and demographic. The agent self-directs the research pipeline from zero prior knowledge.

---

## Skill Identity

```
skill_name: persona-research
version: 1.0
applies_to: Any country, any ethnic/cultural group, any age segment
output_format: Structured JSON (personas file) + optional targeting skill (.md)
dependencies: Web search access, file write access
```

---

## When to Activate This Skill

Activate this skill when the user asks to:
- Build or expand cultural/demographic personas for a new country
- Research consumer behavior, cultural taboos, or generational differences for a nation
- Generate a persona JSON for a specific ethnicity, religion, or age group
- Update an existing personas file with new nations or age segments

---

## Agent Self-Research Pipeline

The agent must follow these phases **in order**. Each phase has explicit search goals and exit criteria.

---

### Phase 1 — Nation & Demographic Discovery

**Goal:** Identify all major ethnic, religious, and demographic groups in the target nation.

**Search queries to run (adapt country name):**

```
"{country} ethnic groups population percentage"
"{country} major religions demographics"
"{country} generational breakdown Gen Z Millennial Gen X population"
"{country} consumer demographics official statistics"
```

**Sources to prioritize:**
- National statistics department (e.g., DOSM for Malaysia, Census Bureau for USA, ONS for UK)
- CIA World Factbook
- Pew Research Center (for religion data)
- Academic journals on demographics

**Exit criteria:** Agent has identified all major ethnic/cultural groups (≥5% population share) and confirmed age group distribution data.

**Output of this phase:**
```json
{
  "country": "...",
  "ethnic_groups": ["group_a", "group_b", "group_c"],
  "age_group_distribution": { "gen_z": "X%", "millennial": "Y%" },
  "primary_languages": ["..."],
  "dominant_religions": ["..."]
}
```

---

### Phase 2 — Cultural Deep Research Per Group

**Goal:** For each ethnic/cultural group, research core values, taboos, behaviors, and historical context.

**Run these searches per group (replace `{group}` and `{country}`):**

```
"{group} {country} cultural values beliefs"
"{group} {country} advertising taboos sensitivities"
"{group} {country} consumer behavior purchasing habits"
"{group} {country} religion sacred symbols do not use"
"{group} {country} cultural nuances marketing"
"{group} {country} historical context identity"
```

**Also search for cross-cutting sensitivities:**
```
"{country} multicultural advertising guidelines"
"{country} banned advertising content cultural"
"{country} ASA/advertising standards {country} cultural rules"
```

**Sources to prioritize:**
- Academic papers (Google Scholar, ResearchGate)
- National advertising standards authority publications
- Market research firms (Nielsen, Kantar, Ipsos, Mintel)
- Country/region-specific marketing blogs with cited data

**Exit criteria:** Agent has at least 3 independent sources per group confirming taboos and core values.

**Per-group output schema:**
```json
{
  "demographics": { "ethnicity": "...", "religion": "...", "location": "...", "primary_language": "...", "key_traits": "..." },
  "historical_and_cultural_context": "...",
  "core_values": ["...", "..."],
  "strict_taboos": ["NEVER ...", "NEVER ..."],
  "nuances_and_behavior": ["...", "..."]
}
```

---

### Phase 3 — Generational Layer Research Per Group

**Goal:** For each ethnic group, research how behavior, values, and media habits differ across age groups.

**Age group keys and birth year ranges:**

| Key | Born | Age (current year) |
|---|---|---|
| `gen_z` | 1997–2012 | ~13–28 |
| `millennial` | 1981–1996 | ~29–44 |
| `gen_x` | 1965–1980 | ~45–60 |
| `baby_boomer` | 1946–1964 | ~61–79 |
| `silent_gen` | Before 1946 | 80+ |

**Search queries per group + generation:**

```
"{country} Gen Z consumer behavior {current_year}"
"{country} Millennial spending habits values"
"{country} Gen X brand loyalty purchasing"
"{country} Baby Boomer digital adoption media"
"{country} elderly senior consumer behavior"
"{group} {country} youth digital media usage"
"{group} {country} older generation traditional values"
```

**Per-age-group output schema (nested inside each ethnic group):**
```json
{
  "age_range": "Born XXXX-XXXX | Age ~XX-XX",
  "label": "{Ethnicity} {Gen} — {Descriptive Title}",
  "tone_and_language": "...",
  "key_motivations": ["...", "..."],
  "preferred_channels": ["...", "..."],
  "content_style": "...",
  "brand_trust_signals": "...",
  "spending_behavior": "...",
  "overrides": {
    "communication_style": "...",
    "digital_literacy": "...",
    "religious_expression": "..."
  }
}
```

**Exit criteria:** Agent has age-specific data for at least 3 of 5 age groups per ethnic group. Missing groups default to closest adjacent group with a note.

---

### Phase 4 — Cross-Validate & Gap-Fill

**Goal:** Verify findings against conflicting sources. Fill in any empty age groups or missing taboos.

**Run these validation searches:**
```
"{country} {group} taboos myths misconceptions debunked"
"{country} generational marketing research academic"
"{country} {group} consumer survey report {current_year}"
```

**Conflict resolution rule:**
- If 2+ authoritative sources agree → include as confirmed fact
- If sources conflict → include both perspectives with a `"note"` field flagging the conflict
- If data is unavailable → mark field as `"_research_needed": true` rather than fabricating

---

### Phase 5 — Assemble Final JSON

**Goal:** Compile all researched data into the standard personas JSON format.

**Full output structure:**

```json
{
  "_meta": {
    "country": "...",
    "version": "1.0",
    "last_updated": "YYYY-MM-DD",
    "usage_guide": "Select persona by: personas[ethnicity].age_groups[age_group_key]. Base persona always applies. Age group OVERRIDES or EXTENDS fields when more specific behavior is needed.",
    "age_group_keys": {
      "gen_z": "Born 1997-2012 | Age ~13-28",
      "millennial": "Born 1981-1996 | Age ~29-44",
      "gen_x": "Born 1965-1980 | Age ~45-60",
      "baby_boomer": "Born 1946-1964 | Age ~61-79",
      "silent_gen": "Born before 1946 | Age 80+"
    },
    "research_sources": ["source1", "source2"],
    "confidence_notes": "Fields marked _research_needed require further validation."
  },
  "{ethnicity_key}": {
    "demographics": { ... },
    "historical_and_cultural_context": "...",
    "core_values": [ ... ],
    "strict_taboos": [ ... ],
    "nuances_and_behavior": [ ... ],
    "age_groups": {
      "gen_z": { ... },
      "millennial": { ... },
      "gen_x": { ... },
      "baby_boomer": { ... },
      "silent_gen": { ... }
    }
  }
}
```

---

## Persona Targeting Logic (Reusable Across All Nations)

Once the JSON is built, this logic applies universally regardless of country.

### Resolve Ethnicity Key

```python
def resolve_ethnicity(raw_input: str, country_map: dict) -> str:
    """
    country_map is loaded from _meta or a separate mapping file per nation.
    Example for Malaysia: {"malay": "malay", "bumiputera": "malay", "chinese": "chinese", ...}
    Example for India: {"hindi": "hindi_speaking", "tamil": "tamil", "sikh": "punjabi", ...}
    """
    return country_map.get(raw_input.lower().strip(), "unknown")
```

### Resolve Age Group Key

```python
def resolve_age_group(birth_year: int, current_year: int = 2026) -> str:
    age = current_year - birth_year
    if age <= 28:
        return "gen_z"
    elif age <= 44:
        return "millennial"
    elif age <= 60:
        return "gen_x"
    elif age <= 79:
        return "baby_boomer"
    else:
        return "silent_gen"
```

### Merge Persona (Base + Age Layer)

```python
def get_persona(personas: dict, ethnicity_key: str, birth_year: int) -> dict:
    """
    Base rules (strict_taboos, core_values, nuances) ALWAYS apply.
    Age layer EXTENDS and OVERRIDES age-specific fields only.
    strict_taboos can NEVER be removed by any age override.
    """
    base = personas[ethnicity_key]
    age_key = resolve_age_group(birth_year)
    age_layer = base["age_groups"].get(age_key, {})

    return {
        "ethnicity": ethnicity_key,
        "age_group": age_key,
        "label": age_layer.get("label", ""),
        # BASE — always enforced
        "strict_taboos": base["strict_taboos"],
        "core_values": base["core_values"],
        "historical_context": base["historical_and_cultural_context"],
        "nuances_and_behavior": base["nuances_and_behavior"],
        # AGE-SPECIFIC
        "tone_and_language": age_layer.get("tone_and_language", ""),
        "key_motivations": age_layer.get("key_motivations", []),
        "preferred_channels": age_layer.get("preferred_channels", []),
        "content_style": age_layer.get("content_style", ""),
        "brand_trust_signals": age_layer.get("brand_trust_signals", ""),
        "spending_behavior": age_layer.get("spending_behavior", ""),
        "overrides": age_layer.get("overrides", {}),
    }
```

### Build Prompt Injection (Universal)

```python
def build_persona_prompt(persona: dict) -> str:
    taboos = "\n".join(f"  - {t}" for t in persona["strict_taboos"])
    values = "\n".join(f"  - {v}" for v in persona["core_values"])
    nuances = "\n".join(f"  - {n}" for n in persona["nuances_and_behavior"])
    motivations = "\n".join(f"  - {m}" for m in persona["key_motivations"])
    channels = ", ".join(persona["preferred_channels"])
    overrides = "\n".join(f"  - [{k}]: {v}" for k, v in persona["overrides"].items())

    return f"""
## Target Persona
- Ethnicity: {persona['ethnicity']}
- Age Group: {persona['label']} ({persona['age_group']})

## Cultural Context
{persona['historical_context']}

## Core Values
{values}

## ABSOLUTE TABOOS — NEVER VIOLATE
{taboos}

## Behavioral Nuances
{nuances}

## Age-Specific Profile
- Tone & Language: {persona['tone_and_language']}
- Key Motivations:
{motivations}
- Preferred Channels: {channels}
- Content Style: {persona['content_style']}
- Brand Trust Signals: {persona['brand_trust_signals']}
- Spending Behavior: {persona['spending_behavior']}

## Age Overrides (Replace General Rules Where Listed)
{overrides if overrides else "  None — base rules fully apply."}
""".strip()
```

---

## Expanding to a New Nation — Agent Checklist

When tasked with a new country (e.g., Indonesia, India, Nigeria, Japan), the agent must:

- [ ] **Run Phase 1** — identify all major ethnic/demographic groups (≥5% pop share)
- [ ] **Run Phase 2** — research cultural values, taboos, history per group (3+ sources each)
- [ ] **Run Phase 3** — research generational differences per group (Gen Z through Silent)
- [ ] **Run Phase 4** — cross-validate and flag any conflicting or missing data
- [ ] **Run Phase 5** — assemble the complete JSON using the standard schema
- [ ] **Verify** — JSON is valid, all `strict_taboos` use "NEVER" prefix, all age groups have `overrides` key
- [ ] **Output** — deliver `{country}_personas.json` + update ethnicity key map in `_meta`

---

## Nation-Specific Notes Template

When building for a new country, add a `_nation_notes` block to `_meta`:

```json
"_nation_notes": {
  "sensitivities": "Key political/religious sensitivities unique to this nation",
  "language_complexity": "Multilingual? Dialects? Official vs spoken language gaps?",
  "digital_landscape": "Internet penetration, dominant platforms, e-commerce maturity",
  "advertising_regulations": "Key legal restrictions (e.g., alcohol ads, religious imagery laws)",
  "research_gaps": "List any demographic groups where data was unavailable or thin"
}
```

---

## Supported Nations (Expandable)

| Country | File | Status |
|---|---|---|
| Malaysia | `malaysia_personas_complete.json` | ✅ Complete |
| Singapore | `singapore_personas.json` | ✅ Partial (Chinese only) |
| Any other nation | `{country}_personas.json` | 🔲 Run this skill to generate |

---

## File Naming Convention

```
{country_iso2}_personas.json        e.g., my_personas.json, sg_personas.json, id_personas.json
persona-research-skill.md           This skill file (universal, reuse for any nation)
persona-targeting.md                Targeting logic (universal, works with any personas JSON)
```

---

## Quality Gates

Before finalizing any personas JSON, verify:

- [ ] All `strict_taboos` entries start with "NEVER"
- [ ] All ethnic groups have at least `core_values`, `strict_taboos`, and `nuances_and_behavior`
- [ ] All age groups have at least `key_motivations`, `preferred_channels`, and `overrides`
- [ ] No fabricated data — all values sourced from Phase 1–4 research
- [ ] Fields with no data use `"_research_needed": true` rather than empty strings or guesses
- [ ] `_meta.research_sources` lists at least 3 source URLs used
