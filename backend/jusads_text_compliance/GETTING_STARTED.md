# Getting Started with JusAds Text Compliance

Welcome! This guide will help you get started with the simplified text compliance checker.

## What You've Got

A clean, easy-to-use text compliance checker that:
- ✅ Evaluates ad text against Malaysian regulatory rules (MCMC)
- ✅ Checks cultural sensitivities (Malay, Chinese, Indian)
- ✅ Uses personas to understand target audience context
- ✅ Gives you a risk score (Low/Medium/High) with specific violations
- ✅ Suggests fixes for non-compliant content

## Quick Start (5 minutes)

### Step 1: Verify Setup

```bash
cd backend/
python -m jusads_text_compliance.test_setup
```

If you see "✓ SETUP TEST PASSED", you're ready to go!

If not, the test will tell you what's missing:
- Missing env vars? Add them to `backend/.env`
- Missing Qdrant collections? Run the ingestion scripts shown

### Step 2: Export Personas (Optional but Recommended)

This creates local JSON files so you can easily see what personas look like:

```bash
python -m jusads_text_compliance.export_personas
```

Check `personas/malaysia_personas.json` to see the cultural personas.

### Step 3: Try Your First Compliance Check

```bash
python -m jusads_text_compliance.cli \
  --text "Try our new whitening cream today! Get fairer skin in just 7 days."
```

You'll see:
- Risk Level (Low/Medium/High)
- Score (0-100)
- List of violations (if any)
- Explanation of issues
- Suggestions to fix them

### Step 4: Try Different Ethnicities

```bash
# Check for Malay audience (Islamic sensitivities)
python -m jusads_text_compliance.cli \
  --text "Win big at our casino this weekend!" \
  --ethnicity malay

# Check for Chinese audience (numerology, symbolism)
python -m jusads_text_compliance.cli \
  --text "Unit #14-04, call 444-4444" \
  --ethnicity chinese

# Check for Indian audience (religious symbols, caste)
python -m jusads_text_compliance.cli \
  --text "Our premium leather shoes" \
  --ethnicity indian
```

## Understanding the Output

```
Risk Level:   Medium
Score:        62/100

VIOLATIONS
- [Religious Sensitivity] (Severity: Severe, Source: cultural): 
  The phrase "casino" violates Islamic principles as gambling is haram...

EXPLANATION
The ad promotes gambling which is prohibited for Muslim audiences...

SUGGESTION
Remove references to gambling or specifically target non-Muslim segments...
```

## What Gets Checked?

### 1. Regulatory Rules (MCMC for Malaysia)
- Misleading claims
- Health product regulations
- Financial services compliance
- Alcohol/tobacco restrictions
- etc.

### 2. Cultural Guidelines (Ethnicity-Specific)

**Malay (Muslim):**
- Halal compliance (no pork, alcohol)
- Modesty (body exposure, clothing)
- Religious sensitivity (mosque imagery, Quran verses)
- Gender interaction (physical contact between non-mahram)

**Chinese:**
- Number symbolism (4 = death, 8 = prosperity)
- Color symbolism (white = mourning)
- Gift taboos (clocks, scissors)
- Ancestral respect

**Indian (Hindu):**
- Sacred symbols (Om, deities)
- Food taboos (beef, cow reverence)
- Caste sensitivity
- Religious festivals (vegetarian periods)

### 3. Persona Context

Each ethnicity has a detailed persona that describes their cultural values and expectations. The LLM uses this to understand "how would a Malay Muslim viewer react to this ad?"

## Tips for Writing Compliant Ads

1. **Start broad, then narrow**: Check with `--ethnicity all` first, then drill down
2. **Use --show-rules**: See which specific rules are being applied
3. **Iterate**: Fix violations one by one and re-test
4. **Export personas**: Read them to understand your audience better
5. **Test edge cases**: Numbers, colors, religious terms, food items

## Common Scenarios

### Scenario 1: Multi-Ethnic Campaign
```bash
# Test the same ad for all three ethnicities
python -m jusads_text_compliance.cli --text "Your ad" --ethnicity malay
python -m jusads_text_compliance.cli --text "Your ad" --ethnicity chinese
python -m jusads_text_compliance.cli --text "Your ad" --ethnicity indian
```

### Scenario 2: Batch Testing
Create a Python script:
```python
from jusads_text_compliance.text_checker import TextComplianceChecker

checker = TextComplianceChecker()

ads = [
    "Try our new whitening cream!",
    "Win cash prizes this weekend!",
    "Premium leather goods on sale",
]

for ad in ads:
    result = checker.check_compliance(ad, ethnicity="malay")
    print(f"{ad[:40]}: {result['risk_level']} ({result['score']}/100)")
```

### Scenario 3: JSON Output for Automation
```bash
python -m jusads_text_compliance.cli \
  --text "Your ad" \
  --ethnicity malay \
  --json > result.json
```

## Next Steps

1. **Read the personas**: Open `personas/malaysia_personas.json`
2. **Check your real ads**: Run compliance on your actual ad copy
3. **Explore the code**: It's simple and well-commented
4. **Integrate with your workflow**: Use the Python API in your scripts
5. **Provide feedback**: What's working? What's confusing?

## Troubleshooting

### "Failed to initialize checker"
→ Run `python -m jusads_text_compliance.test_setup` to diagnose

### "No persona found for X/Y"
→ Run `python -m culture_compliance.ingest_personas` to populate personas

### "Empty results from Qdrant"
→ Verify collections exist: run ingestion scripts from `culture_compliance/`

### "Gemini API error"
→ Check your `GOOGLE_API_KEY` in `.env`

## Getting Help

- **Full documentation**: See `README.md` in this directory
- **Code examples**: Check `cli.py` and `text_checker.py`
- **Qdrant data**: Export personas or query Qdrant directly
- **Issues**: Open a GitHub issue with your error message

---

Happy compliance checking! 🎯
