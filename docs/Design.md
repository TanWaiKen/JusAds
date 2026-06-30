Design Specification: Relume Animated Timeline Hero Section (Upscaled Typography)
1. Global Styles
Colors & "Neon" Effects
Text (Primary): Near black (#111111 or #000000)

Background (Base): Light warm gray/off-white (#F5F5F5 or similar)

Background (Neon Gradients):

Bottom Left: Soft peach/coral glow (#F6A88B approximately). Apply a very heavy radial blur/filter (e.g., blur(120px)) to create a diffuse neon ambient light effect.

Bottom Right: Soft lavender/purple glow (#B590E4 approximately). Apply the same heavy radial blur.

Button (Secondary - Outline): Background White (#FFFFFF), Border Dark (#111111), Text Dark (#111111)

Button (Primary - Solid): Background Dark (#111111), Text White (#FFFFFF)

Texture: The entire background features a subtle, uniform film grain (noise) overlay blended with the neon glows.

2. Typography & Spacing System (Strict Rules)
To ensure high impact and proper vertical rhythm, enforce the following typographic scale (assuming a 16px base) and spacing gaps:

Font Family: Modern sans-serif (e.g., Inter, system-ui).

H1 (Main Title):

Size: 5rem (80px) - Upscaled for impact

Weight: Semi-Bold

Line-height: 1.1

Letter-spacing: -0.02em

H2 (Section Headings - if applicable):

Size: 3.5rem (56px)

Weight: Semi-Bold

Line-height: 1.2

H3 (Card/Minor Headings - if applicable):

Size: 2.25rem (36px)

Weight: Medium

Line-height: 1.3

Subtitle (e.g., "Made for the Webflow community"):

Size: 1.75rem (28px)

Weight: Medium

Line-height: 1.4

Body Text:

Size: 1.125rem (18px)

Weight: Regular

Line-height: 1.6

Spacing (Vertical Rhythm):

Use a base-8 spacing scale.

Gap between H1 and Subtitle: 1.5rem (24px)

Gap between Subtitle and Body Text: 2.5rem (40px)

Gap between Header Nav and Hero Content: Minimum 8rem (128px) to ensure the hero is perfectly centered.

3. Layout & Component Breakdown
A. Navigation Bar (Header)
Position: Top, full width, transparent background.

Padding: 1.5rem 3rem (24px 48px).

Display: Flexbox (justify-content: space-between, align-items: center).

Left Element - Logo: Isometric open box/cube logo in solid black alongside bold text "Relume".

Right Element - Actions (Button Group): Flex container with a 0.75rem (12px) gap.

Button 1 (Visit Relume Library): Icon + Text. Outline style, 0.75rem 1.25rem padding, 4px border-radius.

Button 2 (Clone): Icon + Text. Solid black style, 0.75rem 1.25rem padding, 4px border-radius.

B. Hero Section
Position: Centered vertically and horizontally.

Display: Flex column, align-items: center, text-align: center.

Content Flow (Applying the Spacing System):

Main Heading (H1): "Animated Timeline". The word "Timeline" must have a hand-drawn, curved black SVG stroke positioned absolutely beneath it.

Apply 24px bottom margin.

Subtitle: "Made for the Webflow community".

Apply 40px bottom margin.

Body Text: "We use this timeline component to tell the Relume story..." Constrain the max-width to 600px so the text wraps neatly onto three lines.

Do you want to establish a similar set of rules for a mobile responsive breakpoint (e.g., scaling the H1 down to 3.5rem for smaller screens) before you feed this to the AI?