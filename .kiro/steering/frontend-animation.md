---
inclusion: fileMatch
fileMatchPattern: "frontend/src/**/*.tsx"
---

# Frontend Animation — GSAP Conventions

This project uses GSAP 3.15 with `@gsap/react` for all non-trivial UI animations. Animations should feel purposeful and polished — never gratuitous.

## When to Use GSAP vs. CSS

| Use GSAP | Use CSS/Tailwind |
|----------|-----------------|
| Multi-step sequences or timelines | Single-property hover transitions (e.g., `hover:opacity-80`) |
| Staggered list/grid entrances | Simple `transition-colors` or `transition-opacity` |
| Scroll-triggered reveals | Toggling visibility with Tailwind classes |
| Number count-up animations | Spinner keyframes (`@keyframes`) |
| Coordinated page-entrance choreography | Focus ring or outline transitions |

If an animation involves more than one property, a delay/stagger, or sequencing — use GSAP.

## Required React Pattern

All GSAP animations in React MUST use the `useGSAP` hook with a scoped container ref:

```tsx
import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";

gsap.registerPlugin(useGSAP);

function MyComponent() {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    gsap.from(".card", {
      y: 30,
      opacity: 0,
      stagger: 0.1,
      duration: 0.5,
      ease: "power2.out",
    });
  }, { scope: containerRef });

  return <div ref={containerRef}>...</div>;
}
```

### Rules

- Always pass `{ scope: containerRef }` — never animate without a scope.
- Call `gsap.registerPlugin(...)` at module level for any plugin used (ScrollTrigger, Flip, etc.).
- `useGSAP` handles cleanup automatically — do not manually kill tweens.
- For event-driven animations (hover, click), use `contextSafe` from the `useGSAP` return value:

```tsx
const { contextSafe } = useGSAP(() => {}, { scope: containerRef });

const onHover = contextSafe(() => {
  gsap.to(".card", { scale: 1.03, duration: 0.2 });
});
```

## Standard Animation Patterns

| Pattern | Implementation |
|---------|---------------|
| Page entrance | `gsap.from(".content", { y: 20, autoAlpha: 0, duration: 0.5, ease: "power2.out" })` |
| Card grid stagger | `gsap.from(".card", { y: 30, autoAlpha: 0, stagger: 0.08, duration: 0.4 })` |
| Score count-up | `gsap.to(obj, { value: target, duration: 1.2, ease: "power1.out", onUpdate: render })` |
| Chart reveal | `gsap.from(".chart", { scale: 0.95, autoAlpha: 0, duration: 0.6 })` |
| Compliance results | Timeline: score fades in → violations stagger in → summary slides up |
| Scroll section reveal | ScrollTrigger with `start: "top 80%"`, `toggleActions: "play none none none"` |

## Default Values

Use these unless design requires otherwise:

- **Duration**: 0.4–0.6s for entrances, 0.2–0.3s for hover/micro-interactions
- **Ease**: `"power2.out"` for entrances, `"power1.inOut"` for hover
- **Stagger**: 0.08–0.12 for grids, 0.05 for small lists
- **autoAlpha**: Prefer `autoAlpha` over `opacity` (sets `visibility: hidden` at 0)

## Performance Rules

- Animate only `transform` and `opacity` properties — use GSAP shorthands: `x`, `y`, `scale`, `rotation`, `autoAlpha`.
- Never animate `width`, `height`, `top`, `left`, `margin`, or `padding`.
- Apply `will-change: transform` in CSS on elements that animate frequently.
- For large staggered lists (>20 items), batch with `ScrollTrigger.batch()` instead of animating all at once.
- Avoid `.invalidate()` loops — if data changes, kill and recreate the tween.

## Prohibitions

- Never create GSAP tweens outside `useGSAP` or a `contextSafe` callback.
- Never omit the `scope` option in `useGSAP`.
- Never use `gsap.timeline()` without assigning it to a variable (prevents garbage collection issues).
- Never leave `markers: true` in ScrollTrigger configs — dev-only debugging aid.
- Never animate layout-triggering CSS properties when transforms achieve the same visual.
- Never use CSS `transition` for multi-step or sequenced animations — use a GSAP timeline.
- Never import from `gsap/all` — import specific plugins individually.
