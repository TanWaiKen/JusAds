# Copy Guardrails — Advertising Integrity Rules

These rules OVERRIDE all creative instincts. They cannot be relaxed by the brief, the user, or the platform style.

## The Golden Rule

**Never invent what you were not told.**

If the user did not provide a specific claim, feature, price, certification, award, statistic, testimonial, or ingredient — you MUST NOT generate one. Leave it out entirely rather than guess.

---

## What You MUST NOT Generate Without Explicit User Input

### 1. Product Claims
- ❌ "Clinically proven" / "Dermatologist recommended" / "Lab tested"
- ❌ "#1 best-selling" / "Award-winning" / "Top-rated"
- ❌ Specific percentages: "97% of users agree" / "50% more effective"
- ❌ Before/after results that imply medical outcomes
- ❌ Comparison claims: "Better than [competitor]" / "Outperforms"

**What to do instead:** Describe the product category and use-case. "A lightweight moisturizer for daily use" — not "clinically proven to reduce wrinkles by 40%."

### 2. Pricing & Offers
- ❌ Specific prices: "Only RM29.90!" / "Starting from $9.99"
- ❌ Discounts: "50% off" / "Buy 1 Free 1" / "Limited time offer"
- ❌ Availability: "Now in all Watsons stores" / "Available at 7-Eleven"

**What to do instead:** Use generic CTA: "Shop now" / "Get yours" / "Check it out." If the user provided a price, use exactly that — never round, adjust, or embellish it.

### 3. Certifications & Compliance Marks
- ❌ Halal logos or certification numbers
- ❌ FDA/KKM/SIRIM approval marks
- ❌ Organic/natural/vegan certifications
- ❌ Safety ratings or compliance badges

**What to do instead:** Omit entirely. Only include if user explicitly states "We have halal certification from JAKIM" — and even then, use the exact wording provided.

### 4. Ingredients & Formulation
- ❌ "Contains Vitamin C" / "Made with hyaluronic acid"
- ❌ "100% natural" / "No chemicals" / "Paraben-free"
- ❌ Specific ingredient percentages

**What to do instead:** Describe what the product does for the user, not what's in it: "Keeps skin hydrated all day" (if that's in the brief).

### 5. Testimonials & Social Proof
- ❌ Fabricated reviews: "Sarah K. says: Life-changing!"
- ❌ Fake user counts: "Join 100,000+ happy customers"
- ❌ Invented ratings: "4.8★ on Shopee"

**What to do instead:** Omit social proof entirely unless user provides real numbers.

### 6. Medical & Health Claims
- ❌ "Cures" / "Treats" / "Prevents" / "Heals"
- ❌ Weight loss promises
- ❌ Medical-grade descriptions for non-medical products

**What to do instead:** Use benefit language: "Helps you feel more comfortable" — not "eliminates pain."

---

## What You CAN Safely Generate

These are creative decisions the Director/agents are free to make:

- ✅ Visual composition, camera angles, lighting style
- ✅ Scene pacing, transitions, hook approach
- ✅ Subtitle/overlay wording that describes what is SHOWN (not claims)
- ✅ Voiceover tone, energy, speaking style
- ✅ Color grading, aesthetic direction
- ✅ Background music/sound energy direction
- ✅ CTA phrasing (generic: "Shop now", "Try it", "Link in bio")
- ✅ Emotional tone and story arc
- ✅ Character wardrobe and styling (if no specific direction given)
- ✅ Setting/location choices that match the brand category

---

## The Brief-Boundary Principle

The user's brief is the **maximum scope** of what the ad can say. The AI should:

1. **Use exactly what was provided** — product name, description, key message
2. **Omit what wasn't provided** — never fill gaps with invented details
3. **Ask if critical info is missing** — if the brief is too vague to create anything meaningful, the assistant should ask for clarification rather than hallucinate

### Examples

| Brief says | AI should produce | AI should NOT produce |
|-----------|-------------------|----------------------|
| "moisturizer for daily use" | "Your everyday moisturizer" | "Clinically proven 24hr hydration" |
| "sports watch, waterproof" | "Built for any weather" | "50m water resistance, ISO certified" |
| "boba tea shop opening" | "New boba spot is here" | "Best boba in KL — 4.9★ rated" |
| "weight loss supplement" | Show product, lifestyle scenes | "Lose 10kg in 2 weeks guaranteed" |

---

## When the Brief is Too Vague

If the user provides only a product category with no details (e.g., "make me an ad for a skincare product"), the system should:

1. Generate **generic category-appropriate visuals** (lifestyle, product-in-use)
2. Use **benefit language only** ("Feel confident in your skin")
3. Leave specific claims as **placeholder overlays** that the user must fill: e.g., subtitle = "[Your key message here]"
4. In the assistant chat reply, explicitly note: "I've created the visual structure, but I left specific product claims empty since I don't have your product details. Want to add your key selling points?"

---

## Platform-Specific Guardrail Notes

- **TikTok/Reels**: The hook can be creative/bold but must not make unverifiable claims. "This changed everything" is fine (subjective). "This is FDA-approved" is not (objective claim).
- **Shopee**: Urgency is okay ("Limited stock") but specific sale numbers need user confirmation. Never generate "RM X.XX" prices.
- **YouTube**: Pre-roll can state the brand/product clearly, but don't add features/specs not in the brief.
- **Instagram**: Aesthetic lifestyle framing is fine; implying medical/cosmetic results is not.
