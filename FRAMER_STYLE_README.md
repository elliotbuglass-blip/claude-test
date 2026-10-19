# Redesign brief: dark, product-led style inspired by framer.com

## Goal

Restyle the existing website so it shares the look and feel of framer.com: a near-black page, crisp white type, a single electric-blue accent, product UI shown in dark rounded cards, and subtle animations as each section scrolls in.

Keep this site's own content, brand name, logo, routes and functionality. Change the presentation only. Do not copy Framer's copy, logo, images, illustrations or code. Use it as a style reference.

The values below were measured from framer.com's computed styles at a 1440px viewport (October 2026).

---

## 1. Ground rules for the agent

1. **Audit first.** Before editing, find out how the site is styled (plain CSS, Sass, Tailwind, CSS-in-JS, a theme file) and its framework. Then apply the tokens below in the place that already holds the site's styles. Don't add a second styling system.
2. **Tokens first.** Put every colour, radius, font and duration into design tokens (CSS custom properties, or the Tailwind theme / JS theme object if the site uses one). Components should reference tokens, never raw hex values.
3. **Work section by section.** Order: global tokens and base styles, then nav, hero, content sections, footer. Check the site still builds and renders after each step.
4. **Don't break behaviour.** Forms, links, routing, CMS bindings, analytics and SEO meta stay as they are.
5. **Keep it accessible.** Body text must meet WCAG AA contrast. Interactive elements need a visible focus state. All motion must respect `prefers-reduced-motion`.

---

## 2. Design tokens

```css
:root {
  /* Surfaces: almost everything is black or a near-black grey */
  --color-bg:            #000000;  /* page background */
  --color-surface-1:     #111111;  /* card / panel */
  --color-surface-2:     #1E1E1E;  /* raised panel, inputs */
  --color-surface-3:     #242424;  /* secondary buttons, hover fills */
  --color-overlay:       rgba(255, 255, 255, 0.10); /* chips, subtle fills */

  /* Text */
  --color-text:          #FFFFFF;
  --color-text-muted:    rgba(255, 255, 255, 0.60); /* body copy under headings */
  --color-text-subtle:   #999999;  /* labels, meta */
  --color-text-faint:    #666666;  /* disabled, tertiary */

  /* Accents: use sparingly */
  --color-accent:        #0099FF;  /* links, key data values, primary highlight */
  --color-accent-border: rgba(0, 153, 255, 0.42);
  --color-success:       #00BB88;  /* "Live" / "Good" status */
  --color-success-bg:    rgba(0, 187, 136, 0.10);

  /* Lines */
  --border-hairline:     1px solid rgba(255, 255, 255, 0.06); /* card edges, grid dividers */
  --ring-subtle:         0 0 0 1px rgba(255, 255, 255, 0.08);

  /* Radius */
  --radius-xs:   4px;
  --radius-sm:   6px;
  --radius-md:   8px;    /* buttons, inputs, list rows (most common) */
  --radius-lg:   15px;   /* inner panels */
  --radius-xl:   20px;   /* large section cards */
  --radius-pill: 100px;

  /* Type */
  --font-display: "GT Walsheim", "Satoshi", "General Sans", "Inter", system-ui, sans-serif;
  --font-body:    "Inter", system-ui, -apple-system, sans-serif;
  --font-mono:    "JetBrains Mono", ui-monospace, monospace;

  /* Layout */
  --container:    1200px;
  --gutter:       24px;       /* 16px on mobile */
  --section-gap:  160px;      /* vertical space between major sections; ~96px on mobile */

  /* Motion */
  --ease-out:     cubic-bezier(0.22, 1, 0.36, 1);
  --dur-fast:     150ms;
  --dur-reveal:   700ms;
}
```

**Palette rule:** about 95% of the page is black, greys and white. Colour comes from (a) the one blue accent and (b) the product screenshots and imagery inside cards. Don't add more brand colours. If the site already has a brand colour, use it in place of `--color-accent` and drop the blue.

**Fonts:** GT Walsheim is a paid licence. Unless the site already owns it, use a free geometric sans for headings, such as **Satoshi**, **General Sans** (both from Fontshare) or **Inter Display**. Inter and JetBrains Mono are free on Google Fonts.

---

## 3. Typography scale

| Role | Font | Size / line height | Weight | Letter spacing |
|---|---|---|---|---|
| H1 (hero) | display | 54px / 1.0 (clamp 36–56px) | 500 | -0.04em (≈ -2.16px) |
| H2 (section) | display | 44px / 1.1 (clamp 30–44px) | 500 | -0.04em (≈ -1.76px) |
| H3 (card title) | body | 18px / 1.35 | 400 | -0.2px |
| Body | body | 16px / 1.5 | 400 | normal |
| Small / labels | body | 12–14px | 500 | normal |
| Code / terminal | mono | 14px | 400 | normal |

- Headings are tight (line height about 1.0–1.1, negative tracking), short (2 lines max), left-aligned, and often broken deliberately with `<br>`.
- Card text follows a pattern: a **white H3 title**, then 2–3 lines of `--color-text-muted` description.
- Use `font-feature-settings: "ss01", "cv11";` on Inter if available, for a cleaner look.

---

## 4. Components

### Navigation
- Transparent over black, ~64px tall, sticky at the top. Add `backdrop-filter: blur(8px)` and a translucent black background once the user scrolls.
- Left: logo plus a few text links (14px, `--color-text-muted`, white on hover). Dropdowns get a small chevron.
- Right: "Log in" as a plain muted text link, then the primary button (white pill).

### Buttons
- **Primary:** white background, black text, 14px/500, padding `8px 14px`, radius `--radius-md`.
- **Secondary:** `--color-surface-3` background, white text, same size. An icon (e.g. a download arrow) can sit on the right.
- **Text link with arrow:** "Learn more →", white text, the arrow nudges 2px right on hover.
- Hover: lighten or darken 6–8% over `--dur-fast`. No big shadows and no gradients on buttons.

### Section header row
Every section opens the same way: the **H2 on the left** and **one small secondary button on the right**, vertically aligned to the H2's last line (`display:flex; justify-content:space-between; align-items:flex-end`).

### Cards (the core building block)
- Background `--color-surface-1` (or black with a hairline border), border `--border-hairline`, radius `--radius-xl`, overflow hidden.
- Top ~70%: a **visual area** showing a real UI screenshot, mock app panel or product image, inset with padding and its own `--radius-lg`.
- Bottom: H3 + muted description on the left, and a "Start → / Learn more →" text link on the right.
- Product mockups inside cards use the same dark greys (`#1E1E1E`, `#242424`), 8px radii and tiny 10–12px UI text. They should read as real software, not illustrations.

### Bento feature grid ("full platform" section)
- A CSS grid inside one large rounded container, with cells separated by **hairline dividers** (1px `rgba(255,255,255,0.06)`) instead of gaps.
- Mixed cell sizes: e.g. a 3-column grid where some cells span 2 columns or 2 rows.
- Each cell holds a small UI vignette, with a label in the bottom-left corner: "Performance →", "SEO →", etc.
- Mockup content fades to black toward the cell edges (`mask-image: linear-gradient(...)`) so cells feel cropped.

### Logo strip
- Customer / partner logos in white or light grey, single colour, on black. Two rows of four, centred, generous spacing, no boxes around them.

### Hero
- Left-aligned H1 (two lines max), primary + secondary buttons below it, and an optional small "New: Feature →" link at the far right of the button row.
- Below that, a full-width rounded media card (`--radius-xl`, hairline border) with a product video or visual.
- **Signature effect:** a glowing blue focal element in the centre, e.g. an input box with a neon blue border. Recipe:
  ```css
  .glow {
    border: 1px solid var(--color-accent);
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.04);
    box-shadow:
      0 0 0 1px rgba(0, 153, 255, 0.6),
      0 0 24px rgba(0, 153, 255, 0.55),
      0 0 120px rgba(0, 102, 255, 0.35);
  }
  .glow-backdrop { /* radial bloom behind it */
    background: radial-gradient(50% 50% at 50% 50%, rgba(0, 80, 255, 0.35), transparent 70%);
  }
  ```

### Status badges
- Small pill, 10–11px uppercase or title case, e.g. "Live" or "Good": `--color-success` text on `--color-success-bg`, radius `--radius-sm`.

### Glassy inner highlight (optional, for raised controls)
```css
box-shadow: inset 0 1px 1px rgba(255,255,255,0.35), inset 0 -1px 1px rgba(255,255,255,0.35);
```

### Final call to action
- A centred H2 ("Your next idea starts here" style) with one simple interactive element below it (e.g. a signup / prompt input in a `--color-surface-2` card).

---

## 5. Scroll interactions (important)

These measured behaviours are what make the page feel alive. Build them as small reusable utilities, not one-off code.

### 5.1 Reveal on scroll (main effect)
Cards and section blocks start **slightly offset and faded**, then settle into place as they enter the viewport. Framer's values: start at `opacity: 0.2; transform: translateX(-20px)` and animate to `opacity: 1; transform: none`.

Use translateY for most blocks and the subtle translateX(-20px) for cards in a horizontal row.

```css
[data-reveal] {
  opacity: 0.2;
  transform: translateY(24px);
  transition: opacity var(--dur-reveal) var(--ease-out),
              transform var(--dur-reveal) var(--ease-out);
  will-change: opacity, transform;
}
[data-reveal="x"] { transform: translateX(-20px); }
[data-reveal].is-visible { opacity: 1; transform: none; }

@media (prefers-reduced-motion: reduce) {
  [data-reveal] { opacity: 1; transform: none; transition: none; }
}
```

```js
// reveal.js: load once on every page
const io = new IntersectionObserver((entries) => {
  for (const e of entries) {
    if (e.isIntersecting) {
      e.target.classList.add('is-visible');
      io.unobserve(e.target);
    }
  }
}, { rootMargin: '0px 0px -15% 0px', threshold: 0.1 });

document.querySelectorAll('[data-reveal]').forEach((el, i) => {
  // stagger siblings inside the same group
  const idx = [...el.parentElement.children].indexOf(el);
  el.style.transitionDelay = `${Math.min(idx, 4) * 80}ms`;
  io.observe(el);
});
```

On React / Next.js, use **Framer Motion** (`motion` package) with `whileInView` and `viewport={{ once: true, margin: "-15%" }}` instead, and the same values.

### 5.2 Sticky side panel ("agent" section)
A tall section where a **chat / side panel stays pinned** (`position: sticky; top: 120px;`, ~640px tall) on the right while feature cards scroll past on the left. As each card reaches the middle of the viewport, update the sticky panel's content (e.g. swap its text) to match.

- Implementation: a 2-column grid. The left column has the stacked cards, the right has the sticky element. Track the active card with an IntersectionObserver (`rootMargin: '-45% 0px -45% 0px'`) and crossfade the panel content (200–300ms opacity).
- On mobile (<900px), drop the sticky behaviour and put each panel's content inline under its card.

### 5.3 Scroll-scrubbed media / crossfades
Inside some cards, images crossfade or step through variants as you scroll (opacity going smoothly from 0 to 1 tied to scroll position). Keep this to 1–2 places:
- Use CSS scroll-driven animations (`animation-timeline: view()`) where supported, with the static end state as a fallback, or Framer Motion `useScroll` + `useTransform`.

### 5.4 Ambient motion
- Looping product video in the hero card (muted, `playsinline`, autoplay, a small duration badge in the corner).
- Live-feeling mockups: a "Thinking..." shimmer on placeholder text, counters ticking up, a chart line drawing in on reveal.
- Keep all of it subtle. Nothing should bounce, spin or move more than ~24px.

### 5.5 Micro-interactions
- Links/buttons: colour/background transition over 150ms.
- Arrow links: the arrow shifts 2–3px right on hover.
- Cards: on hover the border goes from 0.06 to about 0.12 white opacity. No scale-up and no big shadow.

---

## 6. Layout & spacing

- Centred container, max width `--container` (1200px), side padding `--gutter`.
- Large vertical rhythm: roughly 160px between major sections on desktop and ~96px on mobile.
- Section order to aim for (adapt to the site's content):
  1. Nav
  2. Hero (H1, buttons, large media card)
  3. Logo / social-proof strip
  4. Feature showcase with sticky side panel (5.2)
  5. Bento "everything included" grid
  6. Community / testimonials / gallery card
  7. Final centred call to action
  8. Footer: multi-column muted links on black, small text
- Responsive: below 900px, grids collapse to one column, the sticky behaviour turns off, and headings shrink via `clamp()`. No horizontal scrolling at 375px.

---

## 7. Acceptance checklist

- [ ] All colours, radii, fonts and durations come from tokens; no stray hex values in components.
- [ ] Page background is pure black, and body text is white or 60% white.
- [ ] Only one accent colour (blue, or the site's brand colour) is used, for highlights only.
- [ ] Headings use the display font with tight line height and negative letter spacing.
- [ ] Every section has the "H2 left / small button right" header row.
- [ ] Cards: dark surface, hairline border, 20px radius, visual on top, title + muted text + arrow link below.
- [ ] Reveal-on-scroll works on all major blocks, staggered, plays once, and turns off under `prefers-reduced-motion`.
- [ ] At least one sticky scroll section and the glowing hero focal element are in place.
- [ ] Lighthouse: Performance ≥ 90, Accessibility ≥ 95, CLS < 0.1 (animate only `transform` and `opacity`).
- [ ] Works at 375px, 768px, 1440px; keyboard focus visible everywhere.
- [ ] Existing content, links, forms and SEO metadata unchanged.
