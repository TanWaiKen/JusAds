# Quick Start - JusAds Text Compliance

## What We Just Built ✨

A **simple text compliance checker** for Malaysian advertising that:
- Checks regulatory rules (MCMC) ✓
- Evaluates cultural sensitivities (Malay/Chinese/Indian) ✓
- Uses personas for audience context ✓
- Gives risk scores + specific violations ✓

## Your Next Steps (Follow in Order)

### 1. Test the Setup (2 minutes)

```bash
cd backend/
python -m jusads_text_compliance.test_setup
```

**What this does:**
- ✅ Checks environment variables
- ✅ Tests Qdrant connection
- ✅ Verifies Gemini API works
- ✅ Confirms collections exist

**If it fails:** The script will tell you exactly what's missing.

---

### 2. Export Personas for Review (1 minute)

```bash
python -m jusads_text_compliance.export_personas
```

**What this does:**
- Creates `backend/jusads_text_compliance/personas/malaysia_personas.json`
- Lets you see what each cultural persona looks like
- Helps you understand what the LLM considers when evaluating

**Then:** Open `personas/malaysia_personas.json` and read the Malay persona.

---

### 3. Try Your First Compliance Check (1 minute)

```bash
python -m jusads_text_compliance.cli \
  --text "Win big at our casino this weekend! Plus enjoy our pork buffet!"
```

**What to expect:**
- Risk Level: **High** (gambling + pork for Malay audience)
- Score: Very low (multiple severe violations)
- Detailed explanation of what's wrong

---

### 4. Test Different Scenarios (5 minutes)

#### A. Malay Muslim Audience (Gambling/Alcohol/Modesty)
```bash
python -m jusads_text_compliance.cli \
  --text "Win big at our casino!" \
  --ethnicity malay
```

#### B. Chinese Audience (Number Symbolism)
```bash
python -m jusads_text_compliance.cli \
  --text "Unit #14-04, call 444-4444 to reserve your unit" \
  --ethnicity chinese
```

#### C. Indian Hindu Audience (Religious Sensitivity)
```bash
python -m jusads_text_compliance.cli \
  --text "Premium cow leather shoes, handcrafted quality" \
  --ethnicity indian
```

#### D. See What Rules Are Being Used
```bash
python -m jusads_text_compliance.cli \
  --text "Your ad copy here" \
  --ethnicity malay \
  --show-rules
```

---

### 5. Test Your Own Ad Copy (5 minutes)

```bash
# Replace with YOUR actual ad text
python -m jusads_text_compliance.cli \
  --text "Your actual ad copy goes here..." \
  --ethnicity malay
```

**Tips:**
- Start with `--ethnicity all` to see general issues
- Then drill down to specific ethnicities
- Use `--show-rules` to understand why something was flagged
- Use `--json` if you want to process results programmatically

---

## Understanding the Output

```
Risk Level:   High          ← Low/Medium/High
Score:        25/100        ← 100 = fully compliant

VIOLATIONS
- [Religious Sensitivity] (Severity: Severe, Source: cultural): 
  The phrase "casino" violates Islamic principles...

EXPLANATION
The ad promotes gambling which is prohibited...

SUGGESTION
Remove references to gambling or target non-Muslim segments
```

---

## What Each Ethnicity Checks

### 🕌 Malay (Muslim)
- Halal compliance (no pork, alcohol, gambling)
- Modesty (body exposure, hijab, clothing)
- Religious sensitivity (mosque imagery, Quran)
- Gender interaction (physical contact)

### 🏮 Chinese
- Number symbolism (4 = death, 8 = prosperity)
- Color symbolism (white = mourning, red = fortune)
- Gift taboos (clocks = death, scissors = cutting ties)
- Ancestral respect

### 🕉️ Indian (Hindu)
- Sacred symbols (Om, deities on floors/shoes)
- Food taboos (beef, cow reverence)
- Caste sensitivity
- Religious festivals

---

## Common Questions

### Q: How long does a check take?
**A:** 1-2 seconds per ad.

### Q: Can I check multiple ads at once?
**A:** Use the Python API (see `GETTING_STARTED.md`) or write a simple loop.

### Q: How do I see what rules are stored?
**A:** Run with `--show-rules` flag, or export personas to JSON.

### Q: What if I disagree with a result?
**A:** Review the specific rules being applied (use `--show-rules`). The system is transparent - you can see exactly which guideline triggered the violation.

### Q: Can I add my own rules?
**A:** For now, rules are in Qdrant. Future: we'll add CSV import for custom rules.

---

## Files to Read Next

1. **`backend/jusads_text_compliance/GETTING_STARTED.md`**  
   Detailed guide with examples

2. **`backend/jusads_text_compliance/README.md`**  
   Full technical documentation

3. **`IMPLEMENTATION_SUMMARY.md`** (root folder)  
   What we built and why

4. **`personas/malaysia_personas.json`**  
   Cultural personas used for evaluation

---

## If Something Goes Wrong

### "Failed to initialize checker"
→ Run `python -m jusads_text_compliance.test_setup` to diagnose

### "No persona found"
→ Collections not populated. Run:
```bash
cd backend/
python -m culture_compliance.ingest_personas
```

### "Gemini API error"
→ Check `GOOGLE_API_KEY` in `backend/.env`

### "Qdrant connection failed"
→ Check `QDRANT_URL` and `QDRANT_API_KEY` in `backend/.env`

---

## What's Different from the Old System?

| Old (`culture_compliance/`) | New (`jusads_text_compliance/`) |
|----------------------------|--------------------------------|
| Complex (LangGraph) | Simple (functions) |
| Multi-modal (text/image/video) | Text only |
| Hard to spot-check rules | Easy (JSON export) |
| AWS Lambda ready | Local focus (API later) |
| Production-grade | Learning/prototyping |

**Use new module for:** Text compliance, learning, prototyping  
**Use old module for:** Production, multi-modal (image/video)

---

## Success Checklist

- [ ] Setup test passes
- [ ] Personas exported
- [ ] Tested with sample ads
- [ ] Tested with your own ad copy
- [ ] Understand the output format
- [ ] Read personas JSON file
- [ ] Reviewed violations for one ethnicity

**When all checked:** You're ready to integrate! 🎉

---

## Next: Integration

Once comfortable, integrate into your workflow:

```python
from jusads_text_compliance.text_checker import TextComplianceChecker

checker = TextComplianceChecker()

# Check an ad
result = checker.check_compliance(
    ad_text="Your ad here",
    ethnicity="malay"
)

if result['risk_level'] == 'High':
    print(f"⚠️ HIGH RISK: {result['explanation']}")
elif result['risk_level'] == 'Medium':
    print(f"⚡ MEDIUM RISK: {result['explanation']}")
else:
    print(f"✓ LOW RISK: Score {result['score']}/100")
```

---

**Questions?** Check the documentation files or the inline code comments.

**Ready?** Run that first test: `python -m jusads_text_compliance.test_setup`
