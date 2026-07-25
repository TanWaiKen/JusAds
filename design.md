# JusAds frontend design guide

## Audience and design goal

JusAds is for Malaysian and Southeast Asian SME owners who can use a laptop but may not know advertising or AI terminology. The interface must help them feel confident about three things within the first screen:

1. What JusAds does.
2. How it helps their business.
3. What to click next.

The product must not promise guaranteed sales. It may state practical benefits such as saving content-production time, reducing production cost, reaching local customers more effectively, and helping generate enquiries or sales.

## Language

- Use everyday task language: create, adapt, check, review, publish.
- Avoid unexplained terms such as transcreation, pipeline, deploy, resonance, demographic, high-fidelity, and localization at scale.
- Button labels describe the result: “Create my first free ad”, not “Start deploying”.
- Keep headings short and specific. Supporting text should normally stay below 22 words.
- Use Malaysian examples where they make a feature easier to understand.

## Navigation and hierarchy

- The landing-page hero owns one primary action: “Create my first free ad”.
- “See a sample result” is the secondary action and must lead directly to the before/after example.
- Main product tasks are visible as four clear choices:
  - Create a local social-media ad
  - Adapt an existing ad
  - See trending content ideas
  - Check an ad before publishing
- On mobile, use a single menu button instead of compressing navigation and account actions into the header.
- On signed-in screens, keep the main task, current step, and next action visible. Advanced controls remain available but visually secondary.

## Easy Mode

- Use two visible steps: choose an ad format, then add ad details.
- Format choices use familiar names, one short sentence, and a visual preview. Selecting one opens a concise information preview before continuing.
- Show essential fields first. Put visual settings, reference uploads, brand rules, and safety details under clearly labelled optional sections.
- “Fill the form for me” uses a familiar chat interface. The conversation may choose a format, request missing information, and populate the form while the user remains in control.
- Keep the Easy Mode and Advanced Mode segmented toggle visible at the top of the workspace.

## Accessibility and interaction

- Body text is at least 16px; important explanatory text is 18px where space permits.
- Interactive controls have at least a 44px touch target.
- Every icon-only control has an accessible name and visible focus treatment.
- Dialogs use the dialog role, an accessible title and description, initial focus, Escape-to-close, focus containment, and focus restoration.
- Form inputs use persistent visible labels, clear error text, and disabled submit buttons until valid.
- Respect reduced-motion preferences.

## Visual style

- Keep the existing warm, modern, high-contrast JusAds identity.
- Prefer clear cards, short labels, familiar icons, and generous spacing.
- Use decorative gradients only as background support; they must not compete with the main message.
- Use blue for selected or informative states, green for confirmed/safe states, amber for caution, and red only for errors.

## Responsive rules

- Mobile header: logo plus menu button only.
- Primary and secondary hero actions are full-width on narrow screens.
- Two-column comparisons stack on mobile and keep labels above the visual.
- Avoid fixed heights for translated copy and pricing descriptions.

## Content proof

The core example is:

“Turn one English product poster into five Malaysian social posts in under five minutes.”

Present the workflow in plain language:

“Upload your poster. Choose your customers. Review your local ad.”
