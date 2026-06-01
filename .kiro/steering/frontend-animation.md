---
inclusion: fileMatch
fileMatchPattern: "frontend/src/**/*.tsx"
---

# Frontend Animation Guidelines

This project uses GSAP for professional, polished UI animations. The frontend should feel dynamic and premium — not just static text and cards.

## Animation Philosophy

- Every page transition, card entrance, and data reveal should have purposeful animation
- Use staggered entrances for lists and grids (cards, violations, assets)
- Scroll-triggered animations for landing page sections
- Subtle hover/interaction feedback on buttons and cards
- Loading states should animate smoothly (skeleton → content fade-in)

## GSAP in React — Required Pattern

Always use the `useGSAP` hook from `@gsap/react` for animations:

```tsx
import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";

gsap.registerPlugin(useGSAP);

function MyComponent() {
  const containerRef = useRef(null);

  useGSAP(() => {
    gsap.from(".card", { y: 30, opacity: 0, stagger: 0.1, duration: 0.5 });
  }, { scope: containerRef });

  return <div ref={containerRef}>...</div>;
}
```

## Animation Patterns to Use

- **Page entrances**: `gsap.from()` with y offset + opacity for content sliding in
- **Card grids**: Staggered fade-in (`stagger: 0.08–0.15`)
- **Numbers/scores**: `gsap.to()` counting up from 0 to final value
- **Charts**: Animate scale/opacity on mount
- **Compliance results**: Timeline sequencing — score appears, then violations slide in
- **Hover states**: `gsap.to()` with scale/shadow on mouseenter, reverse on mouseleave
- **ScrollTrigger**: For landing page sections that animate as user scrolls

## Performance Rules

- Animate only `transform` and `opacity` (use `x`, `y`, `scale`, `rotation`)
- Use `autoAlpha` instead of `opacity` for elements that should be hidden
- Never animate `width`, `height`, `top`, `left` when transforms work
- Use `will-change: transform` in CSS for animated elements
- Always clean up — `useGSAP` handles this automatically with scope

## Do Not

- Use CSS transitions for complex multi-step animations — use GSAP timelines
- Animate without a scope ref — always pass `{ scope: containerRef }`
- Forget `gsap.registerPlugin()` for ScrollTrigger or other plugins
- Leave `markers: true` in production ScrollTrigger configs
- Create animations outside of `useGSAP` or `useEffect` in React
