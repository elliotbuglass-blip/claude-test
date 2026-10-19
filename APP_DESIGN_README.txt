# Build brief: signed-in app, Home ("Let's get creative") + Overview dashboard

> **For the coding agent:** this brief describes two pages that users see **after signing in**:
>
> - **Part 1, Home (`/`):** "Let's get creative". A warm off-white page with a soft animated colour gradient (blue, pink, red, orange) glowing up from the bottom and an AI chat box in the centre. Styled after the hero of lovable.dev.
> - **Part 2, Overview (`/overview`):** a dashboard where everything sits inside one large rounded panel tinted in a rich colour taken from the same gradient family, with frosted-glass cards, an icon side rail, an activity chart, a profile card, a featured-project carousel and recent projects.
>
> Both pages share the same tokens, fonts and gradient colours, so they feel like one product. Finished, working references for both pages are included in full in **Appendix A (Home)** and **Appendix B (Overview)** at the bottom of this file. They are plain HTML/CSS/JS with no dependencies. Port them into this project's stack rather than designing from scratch. To preview them, save each appendix as an `.html` file and open it in a browser.
>
> Use lovable.dev as a style reference only. Do not copy its logo, wording, images or code.

# Part 1: Home, "Let's get creative"

---

## 1. What the page is

A full-screen, single-purpose launch pad:

```
┌───────────────────────────────────────────────────────────┐
│ [logo] YourBrand                  [Overview] [Upgrade] (EB) │  ← transparent top bar
│                                                           │
│                    Let's get creative                     │  ← H1, "creative" gets a colour sweep
│              What would you like to make today?           │  ← muted subtitle
│        ┌─────────────────────────────────────────┐        │
│        │ Ask me to create a landing page for…▌   │        │  ← typed, rotating placeholder
│        │ (+)                 Create ⌄  🎤  (↑)    │        │
│        └─────────────────────────────────────────┘        │
│     (Write a launch post) (Design a logo) (Plan…)         │  ← suggestion chips
│ ░░░░▒▒▒▒▓▓▓▓ blue → pink → red → orange glow ▓▓▓▓▒▒▒▒░░░░ │  ← animated aurora, lower ~60%
└───────────────────────────────────────────────────────────┘
```

The top ~30% of the screen is clean off-white. The colour rises from below and wraps around the chat box, which floats in a soft white "valley" in the middle.

---

## 2. Ground rules

1. **Audit first.** Find the app's framework (React/Next.js, Vue, Svelte, plain HTML…), its styling approach (Tailwind, CSS modules, styled-components…), and how routing and auth work. Build the page with those. Don't add a second styling system.
2. **Route:** make this the default authenticated route (e.g. `/` or `/home` when signed in). Signed-out users keep the existing landing or login flow. Don't change auth logic.
3. **Tokens:** add the tokens in §3 to the app's theme or global CSS, and reference them. No raw hex values in components.
4. **Wire up for real:** the chat box must submit to the app's real create/chat endpoint or route (see §6). The avatar opens the existing account menu. "Overview" goes to the Overview dashboard (Part 2). "Upgrade" goes to the existing billing page; hide it for paid users.
5. **Accessibility & performance:** label every input, give every button a visible focus state, respect `prefers-reduced-motion`, and keep Lighthouse Performance ≥ 90 and CLS < 0.1.

---

## 3. Design tokens

```css
:root {
  /* Surfaces & text */
  --color-bg:           #FAF9F6;              /* warm off-white (Lovable uses hsl(45 40% 98%)) */
  --color-surface:      #FFFFFF;              /* chat box */
  --color-text:         #1C1C1C;              /* near-black, not pure black */
  --color-text-muted:   #6B6B6B;
  --color-text-subtle:  #9A9A9A;              /* placeholder */
  --color-border:       rgba(28, 28, 28, 0.10);

  /* Gradient colours (measured from lovable.dev) */
  --g-blue:   #4F88FF;
  --g-sky:    #82BCFF;
  --g-pink:   #FF66F4;
  --g-red:    #FF3029;
  --g-orange: #FE7B02;

  /* Shape */
  --radius-md:  8px;     /* buttons */
  --radius-xl:  16px;
  --radius-2xl: 28px;    /* chat box */

  /* Type */
  --font-display: "Satoshi", "Inter", system-ui, sans-serif;  /* Satoshi: free from fontshare.com */
  --font-body:    "Inter", system-ui, -apple-system, sans-serif;

  /* Depth & motion */
  --shadow-box:    0 1px 2px rgba(0,0,0,.04), 0 8px 24px -8px rgba(0,0,0,.12), 0 24px 60px -20px rgba(40,60,160,.18);
  --shadow-button: inset 0 1px 0 rgba(255,255,255,.16), 0 1px 2px rgba(0,0,0,.2), 0 2px 4px -2px rgba(0,0,0,.2);
  --ease-out:      cubic-bezier(.22, 1, .36, 1);
}
```

Lovable's own font is Camera Plain, which is a paid licence. Satoshi (headings) and Inter (everything else) are free and close in feel. If the platform already has brand fonts, use those.

---

## 4. Typography

| Element | Font | Size | Weight | Letter spacing | Colour |
|---|---|---|---|---|---|
| H1 "Let's get creative" | display | `clamp(38px, 6vw, 56px)`, line height 1.05 | 700 | -0.04em | `--color-text` |
| Subtitle | body | 18px (16px mobile) | 400 | normal | `--color-text-muted` |
| Chat input | body | 16px / 1.5 | 400 | normal | text / `--color-text-subtle` placeholder |
| Buttons, chips | body | 13–14px | 500 | normal | `--color-text` |

Tight negative letter spacing on the H1 is what makes it look premium. Don't skip it.

---

## 5. Components

### 5.1 Top bar
- `position: fixed`, 64px tall, transparent background, 24px side padding.
- **Left:** the platform's logo and name.
- **Right:** an outlined "Overview" link (to the Part 2 dashboard) (1px `--color-border`, radius 8px), a dark "Upgrade" button (`#1C1C1C`, white text, `--shadow-button`), and a round 32px avatar with the user's initials or photo that opens the account menu.
- Under 640px: hide the two buttons (move them into the avatar menu) and keep the logo and avatar.

### 5.2 Aurora background (the signature effect)
Five large coloured circles, blurred heavily so they melt together, slowly drifting. They sit behind the content in the lower ~65% of the hero.

```css
.hero { position: relative; isolation: isolate; overflow: hidden; min-height: 100dvh; display: grid; place-items: center; }
.aurora { position: absolute; inset: 35% -15% -25% -15%; z-index: -2; filter: blur(70px) saturate(130%); }
.blob { position: absolute; border-radius: 50%; animation: drift 20s ease-in-out infinite alternate; will-change: transform; }
.b1 { width: 60%; height: 70%; left: -5%;  top: 0;   background: var(--g-blue); }
.b2 { width: 55%; height: 75%; right: -5%; top: 5%;  background: var(--g-blue);   animation-duration: 24s; animation-delay: -6s; }
.b3 { width: 70%; height: 60%; left: 15%;  top: 35%; background: var(--g-pink);   animation-duration: 26s; animation-delay: -3s; }
.b4 { width: 60%; height: 55%; left: 25%;  top: 60%; background: var(--g-red);    animation-duration: 22s; animation-delay: -9s; }
.b5 { width: 40%; height: 40%; right: 5%;  top: 55%; background: var(--g-orange); animation-duration: 28s; opacity: .7; }
@keyframes drift {
  0%   { transform: translate3d(0,0,0) scale(1); }
  50%  { transform: translate3d(4%,-6%,0) scale(1.08); }
  100% { transform: translate3d(-5%,3%,0) scale(.96); }
}
/* white "valley" behind the chat box + clean off-white top */
.hero::before { content:""; position:absolute; inset:0; z-index:-1; pointer-events:none;
  background:
    radial-gradient(38% 30% at 50% 50%, rgba(250,249,246,.95), rgba(250,249,246,0) 100%),
    linear-gradient(to bottom, var(--color-bg) 0%, var(--color-bg) 22%, rgba(250,249,246,0) 48%); }
```
- Mobile: widen the aurora (`inset: 40% -40% -20% -40%`) so the colour still fills the bottom.
- Reduced motion: stop the drift (keep the colours, static).
- Optional upgrade: Lovable uses an animated WebGL `<canvas>` for a smoother, more fluid gradient. A shader library such as `@paper-design/shaders` (mesh gradient) can do this. Only switch if the CSS version isn't smooth enough, and keep the CSS version as the fallback.

### 5.2b Interactive background: follows the mouse
The background reacts to the cursor in two ways:
1. **Cursor glow:** a soft pink-to-blue glow (~520px circle, blurred) eases toward the cursor wherever it is on the page, including the white top area. It fades in on first mouse move and fades out when the cursor leaves the page.
2. **Parallax:** the whole aurora shifts gently *away* from the cursor (up to ~20px horizontally and ~12px vertically), so the background feels layered.

```html
<!-- inside .hero, directly after .aurora so it paints above the white wash -->
<div class="glow-follow" id="glow" aria-hidden="true"></div>
```
```css
.glow-follow {
  position: absolute; left: 0; top: 0; z-index: -1; pointer-events: none;
  width: 520px; height: 520px; border-radius: 50%;
  background: radial-gradient(circle, rgba(255,102,244,.55) 0%, rgba(79,136,255,.45) 40%, rgba(79,136,255,0) 70%);
  filter: blur(40px); opacity: 0; transition: opacity .8s var(--ease-out); will-change: transform;
}
.glow-follow.on { opacity: 1; }
.aurora { will-change: transform; }
```
```js
(() => {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced || !matchMedia("(pointer: fine)").matches) return;   // mouse/trackpad only
  const hero = document.querySelector(".hero");
  const glow = document.getElementById("glow");
  const aurora = document.querySelector(".aurora");
  const R = glow.offsetWidth / 2;
  let tx = innerWidth / 2, ty = innerHeight * .7, x = tx, y = ty;
  hero.addEventListener("pointermove", e => {
    const r = hero.getBoundingClientRect();
    tx = e.clientX - r.left; ty = e.clientY - r.top;
    glow.classList.add("on");
  });
  hero.addEventListener("pointerleave", () => glow.classList.remove("on"));
  (function tick() {
    x += (tx - x) * .08; y += (ty - y) * .08;          // easing gives the soft "trailing" feel
    glow.style.transform = `translate3d(${x - R}px, ${y - R}px, 0)`;
    aurora.style.transform = `translate3d(${(x / innerWidth - .5) * -40}px, ${(y / innerHeight - .5) * -24}px, 0)`;
    requestAnimationFrame(tick);
  })();
})();
```
- Animate **only `transform`** (never `left`/`top`) so it stays at 60fps. The easing factor `.08` sets how lazily it trails; raise it toward `.2` for snappier.
- Off for touch devices and reduced motion. Optional extra: on phones, drive the same parallax from `deviceorientation` (tilt). iOS requires a permission prompt for this, so only add it if wanted.
- In React, put this logic in a `useEffect` with cleanup (cancel the animation frame, remove listeners), and keep positions in refs rather than state so the page doesn't re-render every frame.

### 5.3 Headline colour sweep
The word **"creative"** gets one sweep of the gradient across it on page load, then settles back to the normal text colour.
```css
.sweep {
  background: linear-gradient(90deg, var(--color-text) 0 33%, var(--g-sky) 40%, #2483FF 45%, var(--g-pink) 50%,
              var(--g-red) 55%, var(--g-orange) 60%, var(--color-text) 67% 100%);
  background-size: 300% 100%; background-position: 100% 0;
  -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: sweep 2.6s var(--ease-out) .5s both;
}
@keyframes sweep { to { background-position: 0 0; } }
```

### 5.4 Chat box
- Width `min(640px, 100%)`, white, radius `--radius-2xl` (28px), 1px `--color-border`, `--shadow-box`. Padding about `18px 14px 12px 20px`.
- **Focus:** the border turns soft blue (`rgba(79,136,255,.5)`) with a 4px pale blue ring (`0 0 0 4px rgba(79,136,255,.12)`).
- **Textarea:** borderless, transparent, starts at 2 rows and **auto-grows** up to ~220px, then scrolls.
- **Bottom row:**
  - Left: a round 34px "+" button for attaching files.
  - Right: a "Create ⌄" mode dropdown (muted text; options are the platform's modes, e.g. Create / Chat / Edit), a mic button for voice input, and a round dark **send** button.
- **Send button:** 25% opacity until there's text, full opacity when ready, and a small press-scale on click.
- **Keyboard:** Enter sends, Shift+Enter adds a new line.
- **Typed placeholder:** cycle through example prompts, typing ~40ms per character, holding 2s, deleting back to "Ask me to create" (~15ms per char), then typing the next. **Stop as soon as the box is focused**, and set a calm static placeholder ("Describe what you want to create…"). Example prompts live in one array so they're easy to edit; tailor them to what the platform makes.

### 5.5 Suggestion chips
- A centred, wrapping row of 3–5 pill buttons under the box: semi-transparent white (`rgba(255,255,255,.7)` + `backdrop-filter: blur(8px)`), 1px border, 13px text.
- Clicking a chip fills the box with that text and focuses it; it does not send.
- Ideally the chips come from the backend (personalised or recent ideas). Otherwise use a static list.

### 5.6 Entrance animation
The H1, subtitle, chat box and chips each fade up 14px in sequence (0.8s, staggered 50 / 150 / 250 / 350ms) on load. With reduced motion they appear instantly.

---

## 6. Behaviour to wire up

| Element | Action |
|---|---|
| Chat submit | Send the prompt (and selected mode + attachments) to the app's existing create/chat API. On success, route to the new project or conversation view. Show a loading state on the send button while waiting; show errors inline under the box. |
| "+" button | Open the existing file-upload flow (or a hidden `<input type="file">`), and show attached files as small removable chips inside the box. |
| Mode dropdown | Accessible menu (`role="menu"`, arrow-key navigation). Hide it if the platform has only one mode. |
| Mic | Use the Web Speech API if supported, writing the transcript into the box. Hide the button when unsupported. |
| Overview / Upgrade / Avatar | Link to the Overview dashboard (Part 2), billing page and account menu. |
| Greeting (optional) | Can personalise the subtitle, e.g. "What would you like to make today, Elliot?" |

Optional, below the fold: a "Recent projects" grid of cards (white, radius 16px, hairline border, thumbnail + title + last edited). The page must still look complete without it. The hero always fills the first screen.

---

## 7. Responsive

- **≥ 1024px:** as described above.
- **640–1023px:** same layout; the chat box is full width with 24px gutters.
- **< 640px:** the H1 shrinks via `clamp`, the subtitle drops to 16px, the top-bar buttons move into the avatar menu, the chips wrap to 2–3 rows, and the aurora widens. No horizontal scroll at 375px.
- Use `100dvh` (with a `100vh` fallback) so mobile browser bars don't cut off the page.

---

## 8. Acceptance checklist

- [ ] Signed-in users land on this page by default; signed-out flow unchanged.
- [ ] Off-white background (`#FAF9F6`), near-black text, gradient glow rising from the bottom, chat box centred.
- [ ] H1 reads "Let's get creative" with tight letter spacing, and "creative" gets the colour sweep on load.
- [ ] The aurora drifts slowly and smoothly, is static under reduced motion, and has no visible banding or jank on a mid-range laptop.
- [ ] With a mouse, the glow smoothly trails the cursor anywhere on the page and the aurora shifts subtly the other way; it's off for touch and reduced motion, with no dropped frames.
- [ ] The placeholder types through examples and stops on focus.
- [ ] Textarea auto-grows; Enter sends and Shift+Enter adds a new line; send is disabled until there's text.
- [ ] Submitting calls the real backend and routes to the result; loading and error states exist.
- [ ] Chips fill the box without sending.
- [ ] All buttons have accessible labels and visible focus; contrast meets WCAG AA.
- [ ] Checked at 375px, 768px and 1440px; no horizontal scroll.
- [ ] Lighthouse: Performance ≥ 90, Accessibility ≥ 95, CLS < 0.1.

---
---

# Part 2: Overview dashboard

## 9. What the page is

The signed-in dashboard, reached from Home's "Overview" link and the side rail. It reuses Part 1's tokens, fonts and gradient colours, but the content sits in **one large rounded panel tinted with a rich colour** (warm terracotta by default). All text on the panel is white, and every card is **frosted glass**. The page's off-white background and a soft aurora peek out around the panel edges, tying it back to Home.

```
┌──────────────────────────────────────────────────────────────────────┐  ← off-white page, aurora glow at edges
│┌──┬────────────────────────────────────────────────────────────────┐│
││▣ │ Overview  (🔥 7-day streak) (✓ 12 projects) (★ Pro)   [search] 🔔 (+ New)││
││⌂ │ ┌──────── Creations (57) ── Time saved (8hr) ┐ ┌── (EB) Name ─ ⤴ ┐ ││
││▦ │ │   •──╮    ╭•╮        ╭•                     │ │ Projects Credits │ ││
││▢ │ │      ╰•──•  ╰•──╮ ╭─╯                       │ │   80      200    │ ││
││▣ │ │ Mon Tue Wed Thu Fri Sat Sun                 │ │ ▬▬▬▬▬▬░░ credits │ ││
││⚙ │ └─────────────────────────────────────────────┘ └──────────────────┘ ││
││  │ ┌──────────── featured artwork ───────────────┐  FEATURED PROJECT    ││
││  │ │                                             │  Summer               ││
││  │ │              ▲▲  (carousel)                 │  Campaign             ││
││  │ │               • ● •                         │  Assets Views Edits   ││
││  │ └─────────────────────────────────────────────┘  [Open project] [Share] ♡ ││
││EB│ Recent projects                                          See all →  ││
││⇥ │ [thumb] [thumb] [thumb] [thumb]                                      ││
│└──┴────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

## 10. Dashboard tokens (add to Part 1's tokens)

```css
/* Lets the panel tint fade smoothly when the featured project changes */
@property --tint-a { syntax: "<color>"; inherits: true; initial-value: #6E2316; }
@property --tint-b { syntax: "<color>"; inherits: true; initial-value: #C8653F; }

:root {
  --on-tint:        #FFFFFF;
  --on-tint-muted:  rgba(255,255,255,.74);
  --on-tint-faint:  rgba(255,255,255,.52);
  --cream:          #F6E7CF;              /* active nav item + primary buttons */
  --glass-bg:       rgba(255,255,255,.10);
  --glass-bg-hover: rgba(255,255,255,.14);
  --glass-border:   rgba(255,255,255,.22);
  --glass-inset:    inset 0 1px 0 rgba(255,255,255,.18);
  --radius-card:    18px;
  --radius-panel:   28px;
}
```

**Panel tint themes** (dark top-left to light bottom-right). Each featured project carries one, and the panel fades to it:

| Theme | `--tint-a` | `--tint-b` |
|---|---|---|
| Terracotta (default) | `#6E2316` | `#C8653F` |
| Ocean | `#16295E` | `#4F7FE0` |
| Plum | `#4A1752` | `#C04FA0` |

Keep tints dark enough that white text passes WCAG AA on the lightest part of the panel. Check any new tint with a contrast checker before adding it.

## 11. Dashboard layout & components

### 11.1 Panel
- `margin: 16px; min-height: calc(100dvh - 32px); border-radius: var(--radius-panel);`
- Background: `radial-gradient(80% 60% at 0% 0%, rgba(255,255,255,.14), transparent 60%), linear-gradient(165deg, var(--tint-a), var(--tint-b))`.
- Shadow: `0 30px 80px -30px rgba(40,20,60,.45), inset 0 0 0 1px rgba(255,255,255,.18)`.
- Grid: `76px` side rail + `1fr` main.
- `transition: --tint-a 1.2s, --tint-b 1.2s` (works because of the `@property` registrations).
- **Mouse spotlight:** a 420px soft white radial highlight (`rgba(255,255,255,.12)`) follows the cursor across the panel via `--mx`/`--my` custom properties, set in a `requestAnimationFrame`. It's the dashboard's version of Home's cursor glow. Mouse only; off for reduced motion.
- Behind the panel, the page is `--color-bg` with a slow aurora (blue, pink, orange blobs, `blur(80px)`) visible at the edges.

### 11.2 Side rail
- `background: rgba(0,0,0,.10)`, a hairline right border, and icons centred in a column.
- Top to bottom: the brand logo mark (gradient square, links Home), then the nav: **Create** (home icon, links to Part 1), **Overview** (active), Projects, Library, Templates, Settings. A spacer, then the user avatar (opens the account menu) and Log out.
- Buttons are 40px squares with 12px radius, icons 18px in `--on-tint-muted`. Hover: `rgba(255,255,255,.12)` background and white icon.
- **Active item:** `--cream` background, dark icon, soft drop shadow, `aria-current="page"`.
- A tooltip label appears to the right on hover/focus.
- Use the app's icon set (e.g. Lucide) at stroke width ~1.7.

### 11.3 Header row
- An H1 "Overview" (display font, 34px, weight 500, -0.03em), then status chips (small pills: white 12% background, 16px white icon circle plus label, e.g. streak, projects this month, plan).
- Right side: a rounded search field (`rgba(0,0,0,.16)` background), an Alerts ghost button, and a cream **"+ New"** pill that goes back to Home (Part 1) to start something.

### 11.4 Glass card (base for every card)
```css
.card {
  border-radius: var(--radius-card); padding: 22px 24px;
  background: var(--glass-bg); border: 1px solid var(--glass-border); box-shadow: var(--glass-inset);
  -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px);
}
```
Card headings use the display font at 20px, weight 400. Values sit in small outlined pills (`border: 1px solid rgba(255,255,255,.35)`).

### 11.5 Row 1: activity chart + profile (grid `1.65fr / 1fr`, gap 22px)
**Activity card:** "Creations [57]" on the left and "Time saved [8hr]" on the right, with a single-series line chart of creations per day for the last 7 days.
- Smooth curve (Catmull-Rom to Bézier), **2px white line**, white dots r=5 with a tint-coloured 2px ring, and a soft white-to-transparent area fill underneath.
- **Direct labels only on a few points** (the peak, the latest, and one notable mid-week point), never on every point. Day labels along the bottom in `--on-tint-faint`. No legend (one series; the card title names it). No y-axis.
- The line **draws in** on load (`stroke-dashoffset`, 1.4s).
- **Hover:** nearest day, then a dashed vertical crosshair plus a dark tooltip ("Thu · **12** creations").
- Redraws on resize (compute from the container width; don't use `preserveAspectRatio="none"`, which distorts the dots).
- In React, a chart library (Recharts, visx) is fine if it reproduces these specs.

**Profile card:** a 60px avatar with a ring, name, @handle · role, and a round share button. Below that, three stats (Projects / Credits / Shares) split by vertical hairlines; the numbers **count up** on load. At the bottom (pushed down with `margin-top: auto`), a **monthly credits** bar: a 6px track with a white-to-cream fill that animates to the % used, and "124 / 200 used". Use `role="progressbar"` with aria values.

### 11.6 Row 2: featured project (same grid)
**Left, artwork carousel:** a large rounded media card (min-height 330px) showing the project's cover image (the demo uses generated SVG sunset/mountain art; in production use the project's real thumbnail). Pill-dot pagination at the bottom centre, with the active dot stretched to 22px.
- **Auto-advances every 7s**, pauses on hover, and clicking a dot jumps to that project.
- **On change:** the image crossfades (1s), the right-hand text fades out and back in with the new project, and **the whole panel tint fades to that project's theme** (§10). This is the "wow" moment.

**Right, project details** (sits on the panel, no card):
- A small uppercase kicker "FEATURED PROJECT" in `--on-tint-faint`.
- The title in the display font at `clamp(40px, 4.4vw, 60px)`, weight 400, line height 1, with a reserved min-height of 2 lines so the layout doesn't jump.
- A hairline divider.
- Three meta stats with small icons: Assets / Views / Edits.
- A 2–3 line description in `--on-tint-muted`.
- Actions: a cream **"Open project"** pill, a glass **"Share preview"** pill, and a round heart **favourite** toggle (`aria-pressed`; it fills white with a red heart when on).

### 11.7 Row 3: recent projects
A "Recent projects" heading with a "See all →" link, then a 4-column grid of glass mini-cards. Each card has a 16:10 rounded thumbnail (real thumbnails in production; the demo uses gradients from the brand colours), a title, and "Edited 2h ago". Hover: slightly lighter glass and a 2px lift.

### 11.8 Motion
- Header, cards and sections **rise in** (14px, 0.8s, staggered ~80ms) on load.
- Panel tint: 1.2s fade. Carousel: 1s crossfade. Chart: 1.4s line draw. Stats: 1.2s count-up. Credits bar: 1.2s fill.
- `prefers-reduced-motion`: no aurora drift, no rise-in, no tint/crossfade transitions, no auto-advance, and numbers shown immediately.

## 12. Dashboard data to wire up

| UI | Data source |
|---|---|
| Header chips | the user's streak, project count this month, plan |
| Creations chart + total | creations per day, last 7 days |
| Time saved | the app's own metric (or remove the pill) |
| Profile card | the user's name, handle, avatar, role, project / credit / share counts, monthly credit usage |
| Featured carousel | 3–5 featured or pinned projects: title, cover image, assets, views, edits, description, tint theme |
| Recent projects | the 4 most recently edited projects: thumbnail, title, updated time |
| Search | the existing project search |
| "+ New", "Create" (rail), logo | link to Home (Part 1) |
| Open project / Share preview / ♡ | existing project page, share flow, favourite API |

Show skeleton states (glass blocks with a soft shimmer) while data loads, and a friendly empty state ("No projects yet. Let's get creative →" linking Home) for new users.

## 13. Dashboard responsive

- **≥ 1100px:** as described above.
- **760–1099px:** rows stack to one column; recent projects become 2 columns.
- **< 760px:** the panel margin drops to 8px, the **rail becomes a horizontal icon bar at the top** (logo, nav icons, avatar; Log out moves into the account menu), the search goes full width, card headings shrink to 16px, the artwork is min 230px tall, and recent projects stay at 2 columns. No horizontal page scroll at 375px.

## 14. Dashboard acceptance checklist

- [ ] Uses the same tokens, fonts and gradient family as Home; the two pages feel like one product.
- [ ] Content sits in one rounded tinted panel with frosted-glass cards and white text that passes AA contrast.
- [ ] The rail shows Overview as active (cream), Create/logo/"+ New" link to Home, and the tooltips work.
- [ ] The chart has a 2px line, ringed dots, a few direct labels only, hover crosshair + tooltip, draws in on load, and redraws on resize.
- [ ] Profile stats count up; the credits bar fills; the progressbar is accessible.
- [ ] The featured carousel auto-advances (paused on hover), the dots work, and **the panel tint fades to each project's theme**.
- [ ] The mouse spotlight follows the cursor over the panel (mouse only, off for reduced motion).
- [ ] Recent projects show real data, with loading skeletons and an empty state.
- [ ] Checked at 375px, 768px and 1440px; the rail becomes a top bar on mobile; no horizontal scroll.
- [ ] Lighthouse: Performance ≥ 90, Accessibility ≥ 95, CLS < 0.1.

---

## Appendix A: Home page reference (`home.html`)

The complete working "Let's get creative" page. Port it into the app's framework, replacing "YourBrand", the initials, the example prompts and chips, and the submit handler (currently `console.log`) with real data and API calls. Its "Overview" link points at `../dashboard-demo/index.html`; change that to the real `/overview` route.

````html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Home</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link href="https://api.fontshare.com/v2/css?f[]=satoshi@500,600,700&display=swap" rel="stylesheet">
<style>
  :root {
    /* Surfaces & text */
    --color-bg: #FAF9F6;            /* warm off-white (Lovable: hsl(45 40% 98%)) */
    --color-surface: #FFFFFF;
    --color-text: #1C1C1C;
    --color-text-muted: #6B6B6B;
    --color-text-subtle: #9A9A9A;
    --color-border: rgba(28, 28, 28, 0.10);

    /* Signature gradient */
    --g-blue: #4F88FF;
    --g-sky: #82BCFF;
    --g-pink: #FF66F4;
    --g-red: #FF3029;
    --g-orange: #FE7B02;

    --radius-md: 8px;
    --radius-xl: 16px;
    --radius-2xl: 28px;

    --font-display: "Satoshi", "Inter", system-ui, sans-serif;
    --font-body: "Inter", system-ui, -apple-system, sans-serif;
    --ease-out: cubic-bezier(.22, 1, .36, 1);

    --shadow-box: 0 1px 2px rgba(0,0,0,.04), 0 8px 24px -8px rgba(0,0,0,.12), 0 24px 60px -20px rgba(40,60,160,.18);
    --shadow-button: inset 0 1px 0 rgba(255,255,255,.16), 0 1px 2px rgba(0,0,0,.2), 0 2px 4px -2px rgba(0,0,0,.2);
  }
  * { box-sizing: border-box; margin: 0; }
  html, body { height: 100%; }
  body { background: var(--color-bg); color: var(--color-text); font-family: var(--font-body); -webkit-font-smoothing: antialiased; }
  button { font: inherit; color: inherit; cursor: pointer; }

  /* ---------- Top bar (signed-in) ---------- */
  .topbar {
    position: fixed; inset: 0 0 auto; z-index: 10; height: 64px;
    display: flex; align-items: center; justify-content: space-between; padding: 0 24px;
  }
  .brand { display: flex; align-items: center; gap: 10px; font: 700 18px var(--font-display); letter-spacing: -.02em; text-decoration: none; color: inherit; }
  .brand-mark { width: 22px; height: 22px; border-radius: 7px; background: linear-gradient(135deg, var(--g-orange), var(--g-pink) 55%, var(--g-blue)); }
  .nav-right { display: flex; align-items: center; gap: 10px; }
  .btn { border: 0; border-radius: var(--radius-md); padding: 8px 12px; font-size: 14px; font-weight: 500; transition: background .15s; }
  a.btn { display: inline-block; text-decoration: none; color: inherit; }
  .btn-ghost { background: transparent; border: 1px solid var(--color-border); }
  .btn-ghost:hover { background: rgba(0,0,0,.04); }
  .btn-dark { background: #1C1C1C; color: #fff; box-shadow: var(--shadow-button); }
  .btn-dark:hover { background: #333; }
  .avatar { width: 32px; height: 32px; border-radius: 50%; border: 0; display: grid; place-items: center; background: #1C1C1C; color: #fff; font-size: 13px; font-weight: 600; }

  /* ---------- Hero ---------- */
  .hero {
    position: relative; isolation: isolate; overflow: hidden;
    min-height: 100vh; min-height: 100dvh;
    display: grid; place-items: center; padding: 96px 16px 120px;
  }

  /* Aurora: drifting colour blobs, blurred together, rising from the lower half */
  .aurora { position: absolute; inset: 35% -15% -25% -15%; z-index: -2; filter: blur(70px) saturate(130%); }
  .blob { position: absolute; border-radius: 50%; animation: drift 20s ease-in-out infinite alternate; will-change: transform; }
  .b1 { width: 60%; height: 70%; left: -5%;  top: 0;   background: var(--g-blue); }
  .b2 { width: 55%; height: 75%; right: -5%; top: 5%;  background: var(--g-blue); animation-duration: 24s; animation-delay: -6s; }
  .b3 { width: 70%; height: 60%; left: 15%;  top: 35%; background: var(--g-pink); animation-duration: 26s; animation-delay: -3s; }
  .b4 { width: 60%; height: 55%; left: 25%;  top: 60%; background: var(--g-red);  animation-duration: 22s; animation-delay: -9s; }
  .b5 { width: 40%; height: 40%; right: 5%;  top: 55%; background: var(--g-orange); opacity: .7; animation-duration: 28s; }
  /* Cursor-following glow: sits above the white wash so it shows anywhere on the page */
  .glow-follow {
    position: absolute; left: 0; top: 0; z-index: -1; pointer-events: none;
    width: 520px; height: 520px; border-radius: 50%;
    background: radial-gradient(circle, rgba(255,102,244,.55) 0%, rgba(79,136,255,.45) 40%, rgba(79,136,255,0) 70%);
    filter: blur(40px); opacity: 0; transition: opacity .8s var(--ease-out);
    will-change: transform;
  }
  .glow-follow.on { opacity: 1; }
  .aurora { will-change: transform; }
  @keyframes drift {
    0%   { transform: translate3d(0, 0, 0) scale(1); }
    50%  { transform: translate3d(4%, -6%, 0) scale(1.08); }
    100% { transform: translate3d(-5%, 3%, 0) scale(.96); }
  }
  /* Soft white "valley" in the middle so the chat box floats in light, like Lovable */
  .hero::before {
    content: ""; position: absolute; inset: 0; z-index: -1; pointer-events: none;
    background:
      radial-gradient(38% 30% at 50% 50%, rgba(250,249,246,.95), rgba(250,249,246,0) 100%),
      linear-gradient(to bottom, var(--color-bg) 0%, var(--color-bg) 22%, rgba(250,249,246,0) 48%);
  }

  .hero-inner { width: min(640px, 100%); text-align: center; }
  .hero h1 {
    font-family: var(--font-display); font-weight: 700;
    font-size: clamp(38px, 6vw, 56px); line-height: 1.05; letter-spacing: -.04em;
  }
  .sweep {
    background: linear-gradient(90deg, var(--color-text) 0 33%, var(--g-sky) 40%, #2483FF 45%, var(--g-pink) 50%, var(--g-red) 55%, var(--g-orange) 60%, var(--color-text) 67% 100%);
    background-size: 300% 100%; background-position: 100% 0;
    -webkit-background-clip: text; background-clip: text; color: transparent;
    animation: sweep 2.6s var(--ease-out) .5s both;
    padding-right: .05em;
  }
  @keyframes sweep { to { background-position: 0 0; } }
  .hero p.sub { margin: 12px 0 32px; font-size: 18px; color: var(--color-text-muted); }

  /* ---------- Chat box ---------- */
  .chat {
    text-align: left; background: var(--color-surface); border-radius: var(--radius-2xl);
    border: 1px solid var(--color-border); box-shadow: var(--shadow-box);
    padding: 18px 14px 12px 20px; transition: box-shadow .2s, border-color .2s;
  }
  .chat:focus-within { border-color: rgba(79,136,255,.5); box-shadow: var(--shadow-box), 0 0 0 4px rgba(79,136,255,.12); }
  .chat textarea {
    display: block; width: 100%; min-height: 52px; max-height: 220px; resize: none; border: 0; outline: 0;
    background: transparent; font: 16px/1.5 var(--font-body); color: var(--color-text);
  }
  .chat textarea::placeholder { color: var(--color-text-subtle); }
  .chat-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 6px; }
  .chat-foot .left, .chat-foot .right { display: flex; align-items: center; gap: 6px; }
  .icon-btn { width: 34px; height: 34px; border-radius: 50%; border: 1px solid var(--color-border); background: #fff; display: grid; place-items: center; transition: background .15s; }
  .icon-btn:hover { background: #F3F2EE; }
  .icon-btn.plain { border-color: transparent; }
  .mode { border: 0; background: transparent; padding: 6px 8px; border-radius: var(--radius-md); font-size: 14px; color: var(--color-text-muted); display: flex; gap: 4px; align-items: center; }
  .mode:hover { background: #F3F2EE; }
  .send { width: 34px; height: 34px; border-radius: 50%; border: 0; display: grid; place-items: center; background: #1C1C1C; color: #fff; opacity: .25; transition: opacity .2s, transform .15s; }
  .send.ready { opacity: 1; }
  .send:active { transform: scale(.92); }
  svg { width: 18px; height: 18px; stroke: currentColor; fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }

  /* Suggestion chips */
  .chips { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 18px; }
  .chip { border: 1px solid var(--color-border); background: rgba(255,255,255,.7); backdrop-filter: blur(8px); border-radius: 999px; padding: 7px 14px; font-size: 13px; color: var(--color-text); transition: background .15s, transform .15s; }
  .chip:hover { background: #fff; transform: translateY(-1px); }

  /* Entrance */
  .rise { opacity: 0; transform: translateY(14px); animation: rise .8s var(--ease-out) forwards; }
  .d1 { animation-delay: .05s } .d2 { animation-delay: .15s } .d3 { animation-delay: .25s } .d4 { animation-delay: .35s }
  @keyframes rise { to { opacity: 1; transform: none; } }

  @media (max-width: 640px) {
    .nav-hide-sm { display: none; }
    .hero p.sub { font-size: 16px; }
    .aurora { inset: 40% -40% -20% -40%; }
  }
  @media (prefers-reduced-motion: reduce) {
    .blob, .sweep, .rise { animation: none; }
    .rise { opacity: 1; transform: none; }
    .sweep { color: var(--color-text); background: none; }
  }
</style>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="#"><span class="brand-mark"></span>YourBrand</a>
    <div class="nav-right">
      <a class="btn btn-ghost nav-hide-sm" href="../dashboard-demo/index.html">Overview</a>
      <button class="btn btn-dark nav-hide-sm">Upgrade</button>
      <button class="avatar" aria-label="Account menu">EB</button>
    </div>
  </header>

  <main class="hero">
    <div class="aurora" aria-hidden="true">
      <span class="blob b1"></span><span class="blob b2"></span><span class="blob b3"></span><span class="blob b4"></span><span class="blob b5"></span>
    </div>
    <div class="glow-follow" id="glow" aria-hidden="true"></div>

    <div class="hero-inner">
      <h1 class="rise d1">Let’s get <span class="sweep">creative</span></h1>
      <p class="sub rise d2">What would you like to make today?</p>

      <form class="chat rise d3" id="chat">
        <label for="prompt" class="sr-only" hidden>Describe what you want to create</label>
        <textarea id="prompt" rows="2" placeholder="Ask me to create…"></textarea>
        <div class="chat-foot">
          <div class="left">
            <button type="button" class="icon-btn" aria-label="Attach file">
              <svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>
            </button>
          </div>
          <div class="right">
            <button type="button" class="mode">Create <svg viewBox="0 0 24 24" style="width:14px;height:14px"><path d="m6 9 6 6 6-6"/></svg></button>
            <button type="button" class="icon-btn plain" aria-label="Voice input">
              <svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>
            </button>
            <button type="submit" class="send" id="send" aria-label="Send">
              <svg viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
            </button>
          </div>
        </div>
      </form>

      <div class="chips rise d4">
        <button class="chip" type="button">Write a product launch post</button>
        <button class="chip" type="button">Design a logo idea</button>
        <button class="chip" type="button">Plan a content calendar</button>
        <button class="chip" type="button">Brainstorm campaign names</button>
      </div>
    </div>
  </main>

<script>
  // Rotating typed placeholder, like Lovable's "Ask Lovable to create a blog about…"
  // Edit these to suit your platform.
  const EXAMPLES = [
    "Ask me to create a landing page for my new candle brand…",
    "Ask me to create 5 Instagram captions for a summer sale…",
    "Ask me to create a moodboard for a coffee shop rebrand…",
    "Ask me to create a short video script about our app…",
  ];
  const box = document.getElementById("prompt");
  const send = document.getElementById("send");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const wait = ms => new Promise(r => setTimeout(r, ms));
  let typing = !reduced;

  async function typeLoop() {
    for (let i = 0; typing; i = (i + 1) % EXAMPLES.length) {
      const text = EXAMPLES[i];
      for (let n = 1; n <= text.length && typing; n++) { box.placeholder = text.slice(0, n); await wait(40); }
      await wait(2000);
      for (let n = text.length; n > 15 && typing; n--) { box.placeholder = text.slice(0, n); await wait(15); }
    }
  }
  if (typing) typeLoop(); else box.placeholder = EXAMPLES[0];

  // Stop the animation once the user engages; restore a calm placeholder.
  box.addEventListener("focus", () => { typing = false; box.placeholder = "Describe what you want to create…"; });

  // Auto-grow textarea + enable send button when there's text.
  box.addEventListener("input", () => {
    box.style.height = "auto"; box.style.height = box.scrollHeight + "px";
    send.classList.toggle("ready", box.value.trim().length > 0);
  });
  // Enter sends, Shift+Enter makes a new line.
  box.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); document.getElementById("chat").requestSubmit(); }
  });

  // Chips fill the box.
  document.querySelectorAll(".chip").forEach(c => c.addEventListener("click", () => {
    typing = false; box.value = c.textContent; box.focus(); box.dispatchEvent(new Event("input"));
  }));

  // Interactive background: a glow eases toward the cursor, and the aurora drifts the
  // opposite way for parallax. Mouse/trackpad only; off for touch and reduced motion.
  (() => {
    if (reduced || !matchMedia("(pointer: fine)").matches) return;
    const hero = document.querySelector(".hero");
    const glow = document.getElementById("glow");
    const aurora = document.querySelector(".aurora");
    const R = glow.offsetWidth / 2;
    let tx = innerWidth / 2, ty = innerHeight * .7, x = tx, y = ty;
    hero.addEventListener("pointermove", e => {
      const r = hero.getBoundingClientRect();
      tx = e.clientX - r.left; ty = e.clientY - r.top;
      glow.classList.add("on");
    });
    hero.addEventListener("pointerleave", () => glow.classList.remove("on"));
    (function tick() {
      x += (tx - x) * .08; y += (ty - y) * .08;   // easing = the "trailing" feel
      glow.style.transform = `translate3d(${x - R}px, ${y - R}px, 0)`;
      aurora.style.transform = `translate3d(${(x / innerWidth - .5) * -40}px, ${(y / innerHeight - .5) * -24}px, 0)`;
      requestAnimationFrame(tick);
    })();
  })();

  // Replace this with your real handler (e.g. POST to your API, then route to the chat/workspace view).
  document.getElementById("chat").addEventListener("submit", e => {
    e.preventDefault();
    const prompt = box.value.trim();
    if (!prompt) return;
    console.log("New request:", prompt);
  });
</script>
</body>
</html>
````

---

## Appendix B: Overview dashboard reference (`overview.html`)

The complete working dashboard. All sample data is in the `WEEK`, `FEATURED` and `RECENT` arrays near the top of the script; replace them with API data. Links to `../home-demo/index.html` should become the real Home route (`/`).

````html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Overview</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link href="https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700&display=swap" rel="stylesheet">
<style>
  /* Animatable tint colours so the whole panel can fade between project themes */
  @property --tint-a { syntax: "<color>"; inherits: true; initial-value: #6E2316; }
  @property --tint-b { syntax: "<color>"; inherits: true; initial-value: #C8653F; }

  :root {
    /* Shared with the "Let's get creative" home page */
    --color-bg: #FAF9F6;
    --color-text-dark: #1C1C1C;
    --g-blue: #4F88FF; --g-sky: #82BCFF; --g-pink: #FF66F4; --g-red: #FF3029; --g-orange: #FE7B02;
    --font-display: "Satoshi", "Inter", system-ui, sans-serif;
    --font-body: "Inter", system-ui, -apple-system, sans-serif;
    --ease-out: cubic-bezier(.22, 1, .36, 1);

    /* Dashboard: text on the tinted panel */
    --on-tint: #FFFFFF;
    --on-tint-muted: rgba(255,255,255,.74);
    --on-tint-faint: rgba(255,255,255,.52);
    --cream: #F6E7CF;                         /* active nav + primary button */

    /* Glass cards */
    --glass-bg: rgba(255,255,255,.10);
    --glass-bg-hover: rgba(255,255,255,.14);
    --glass-border: rgba(255,255,255,.22);
    --glass-inset: inset 0 1px 0 rgba(255,255,255,.18);
    --radius-card: 18px;
    --radius-panel: 28px;
  }
  * { box-sizing: border-box; margin: 0; }
  html, body { min-height: 100%; }
  body { background: var(--color-bg); color: var(--on-tint); font-family: var(--font-body); -webkit-font-smoothing: antialiased; overflow-x: hidden; }
  button, input { font: inherit; color: inherit; }
  button { cursor: pointer; }
  a { color: inherit; text-decoration: none; }
  svg.i { width: 18px; height: 18px; stroke: currentColor; fill: none; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; flex: none; }

  /* ---------- Page aurora (same family as home), peeking around the panel ---------- */
  .aurora { position: fixed; inset: 20% -15% -30% -15%; z-index: -2; filter: blur(80px) saturate(130%); opacity: .8; pointer-events: none; }
  .blob { position: absolute; border-radius: 50%; animation: drift 22s ease-in-out infinite alternate; }
  .b1 { width: 55%; height: 70%; left: -5%; top: 0; background: var(--g-blue); }
  .b2 { width: 60%; height: 60%; left: 25%; top: 40%; background: var(--g-pink); animation-duration: 26s; }
  .b3 { width: 50%; height: 60%; right: -5%; top: 20%; background: var(--g-orange); animation-duration: 24s; }
  @keyframes drift { to { transform: translate3d(5%, -6%, 0) scale(1.08); } }

  /* ---------- Panel ---------- */
  .panel {
    position: relative; isolation: isolate; overflow: hidden;
    margin: 16px; min-height: calc(100dvh - 32px);
    border-radius: var(--radius-panel);
    background:
      radial-gradient(80% 60% at 0% 0%, rgba(255,255,255,.14), transparent 60%),
      linear-gradient(165deg, var(--tint-a) 0%, var(--tint-b) 100%);
    box-shadow: 0 30px 80px -30px rgba(40,20,60,.45), inset 0 0 0 1px rgba(255,255,255,.18);
    display: grid; grid-template-columns: 76px 1fr;
    transition: --tint-a 1.2s var(--ease-out), --tint-b 1.2s var(--ease-out);
  }
  /* Soft spotlight that follows the mouse across the panel */
  .panel::after {
    content: ""; position: absolute; inset: 0; z-index: -1; pointer-events: none;
    background: radial-gradient(420px circle at var(--mx, 70%) var(--my, 20%), rgba(255,255,255,.12), transparent 70%);
  }

  /* ---------- Side rail ---------- */
  .rail { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 22px 0; background: rgba(0,0,0,.10); border-right: 1px solid rgba(255,255,255,.10); }
  .logo { width: 32px; height: 32px; border-radius: 10px; margin-bottom: 26px; background: linear-gradient(135deg, var(--g-orange), var(--g-pink) 55%, var(--g-blue)); box-shadow: 0 0 0 1px rgba(255,255,255,.35); }
  .nav-btn { width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center; color: var(--on-tint-muted); border: 0; background: transparent; transition: background .15s, color .15s; position: relative; }
  .nav-btn:hover { background: rgba(255,255,255,.12); color: #fff; }
  .nav-btn[aria-current="page"] { background: var(--cream); color: var(--color-text-dark); box-shadow: 0 4px 14px -4px rgba(0,0,0,.35); }
  .nav-btn .tip { position: absolute; left: 52px; white-space: nowrap; font-size: 12px; background: rgba(20,20,20,.85); color: #fff; padding: 4px 8px; border-radius: 6px; opacity: 0; transform: translateX(-4px); transition: .15s; pointer-events: none; }
  .nav-btn:hover .tip, .nav-btn:focus-visible .tip { opacity: 1; transform: none; }
  .rail .spacer { flex: 1; }
  .me { width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; font-size: 13px; font-weight: 600; background: linear-gradient(135deg, #FFD9B8, #F5A3C7); color: var(--color-text-dark); box-shadow: 0 0 0 2px rgba(255,255,255,.4); margin-bottom: 6px; }

  /* ---------- Main ---------- */
  main { padding: 28px 32px 36px; min-width: 0; }
  .head { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; margin-bottom: 26px; }
  .head h1 { font: 500 34px/1 var(--font-display); letter-spacing: -.03em; }
  .chips { display: flex; gap: 8px; flex-wrap: wrap; }
  .chip { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; padding: 5px 10px 5px 6px; border-radius: 999px; background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.16); color: var(--on-tint-muted); }
  .chip i { width: 16px; height: 16px; border-radius: 50%; display: grid; place-items: center; font-style: normal; font-size: 10px; background: #fff; color: var(--color-text-dark); }
  .head-actions { margin-left: auto; display: flex; align-items: center; gap: 10px; }
  .search { display: flex; align-items: center; gap: 8px; width: 240px; padding: 8px 12px; border-radius: 999px; background: rgba(0,0,0,.16); border: 1px solid rgba(255,255,255,.12); color: var(--on-tint-muted); }
  .search input { border: 0; outline: 0; background: transparent; width: 100%; font-size: 13px; color: #fff; }
  .search input::placeholder { color: var(--on-tint-faint); }
  .search:focus-within { border-color: rgba(255,255,255,.4); }
  .ghost-btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 12px; border-radius: 999px; border: 0; background: transparent; font-size: 13px; color: var(--on-tint-muted); transition: background .15s, color .15s; }
  .ghost-btn:hover { background: rgba(255,255,255,.12); color: #fff; }
  .cream-btn { display: inline-flex; align-items: center; gap: 6px; padding: 9px 16px; border-radius: 999px; border: 0; background: var(--cream); color: var(--color-text-dark); font-size: 13px; font-weight: 500; box-shadow: 0 6px 18px -8px rgba(0,0,0,.45); transition: transform .15s, filter .15s; }
  .cream-btn:hover { filter: brightness(1.04); transform: translateY(-1px); }
  .glass-btn { display: inline-flex; align-items: center; gap: 6px; padding: 9px 16px; border-radius: 999px; background: var(--glass-bg); border: 1px solid var(--glass-border); font-size: 13px; color: #fff; transition: background .15s; }
  .glass-btn:hover { background: var(--glass-bg-hover); }
  .round-btn { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; background: var(--glass-bg); border: 1px solid var(--glass-border); transition: background .15s, transform .15s; }
  .round-btn:hover { background: var(--glass-bg-hover); }
  .round-btn[aria-pressed="true"] { background: #fff; color: var(--g-red); }
  .round-btn[aria-pressed="true"] svg { fill: currentColor; }

  .grid { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(0, 1fr); gap: 22px; }
  .card {
    position: relative; border-radius: var(--radius-card); padding: 22px 24px;
    background: var(--glass-bg); border: 1px solid var(--glass-border); box-shadow: var(--glass-inset);
    -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px);
  }
  .card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .card-head h2 { font: 400 20px/1.2 var(--font-display); letter-spacing: -.01em; display: flex; align-items: center; gap: 10px; white-space: nowrap; }
  .profile { display: flex; flex-direction: column; }
  .usage { margin-top: auto; padding-top: 22px; }
  .usage-row { display: flex; justify-content: space-between; font-size: 12px; color: var(--on-tint-muted); margin-bottom: 8px; }
  .usage-row b { color: #fff; font-weight: 500; }
  .bar { height: 6px; border-radius: 3px; background: rgba(255,255,255,.18); overflow: hidden; }
  .bar span { display: block; height: 100%; width: 0; border-radius: 3px; background: linear-gradient(90deg, #fff, var(--cream)); transition: width 1.2s var(--ease-out) .4s; }
  .pill { font: 500 13px var(--font-body); padding: 3px 10px; border-radius: 999px; border: 1px solid rgba(255,255,255,.35); color: #fff; }

  /* Activity chart */
  .chart-wrap { position: relative; height: 170px; margin-top: 10px; }
  .chart-wrap svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
  .chart-line { fill: none; stroke: rgba(255,255,255,.92); stroke-width: 2; stroke-linecap: round; }
  .chart-area { fill: url(#areaFill); }
  .chart-dot { fill: #fff; stroke: var(--tint-a); stroke-width: 2; }
  .chart-label { fill: var(--on-tint-muted); font: 500 11px var(--font-body); }
  .chart-x { fill: var(--on-tint-faint); font: 400 11px var(--font-body); }
  .crosshair { stroke: rgba(255,255,255,.45); stroke-width: 1; stroke-dasharray: 3 3; opacity: 0; transition: opacity .15s; }
  .tooltip { position: absolute; pointer-events: none; transform: translate(-50%, calc(-100% - 12px)); background: rgba(20,14,14,.82); color: #fff; font-size: 12px; padding: 6px 9px; border-radius: 8px; white-space: nowrap; opacity: 0; transition: opacity .15s; backdrop-filter: blur(6px); }
  .tooltip b { font-weight: 600; }

  /* Profile card */
  .profile-top { display: flex; align-items: center; gap: 16px; }
  .avatar-lg { width: 60px; height: 60px; border-radius: 50%; display: grid; place-items: center; font: 600 20px var(--font-display); color: var(--color-text-dark); background: linear-gradient(135deg, #FFD9B8, #F5A3C7 60%, #A9C4FF); box-shadow: 0 0 0 3px rgba(255,255,255,.35); }
  .profile-top .who { flex: 1; min-width: 0; }
  .who b { display: block; font-weight: 500; font-size: 15px; }
  .who span { font-size: 12px; color: var(--on-tint-muted); }
  .stats3 { display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 26px; }
  .stats3 > div { text-align: center; padding: 4px 0; }
  .stats3 > div + div { border-left: 1px solid rgba(255,255,255,.18); }
  .stats3 small { display: block; font-size: 13px; color: var(--on-tint-muted); margin-bottom: 8px; }
  .stats3 strong { font: 400 22px var(--font-display); }

  /* Featured project */
  .feature-media { position: relative; overflow: hidden; border-radius: var(--radius-card); min-height: 330px; border: 1px solid var(--glass-border); box-shadow: 0 20px 50px -24px rgba(0,0,0,.5); }
  .art { position: absolute; inset: 0; transition: opacity 1s var(--ease-out); }
  .art:not(.on) { opacity: 0; }
  .art svg { width: 100%; height: 100%; display: block; }
  .dots { position: absolute; left: 50%; bottom: 16px; transform: translateX(-50%); display: flex; gap: 8px; }
  .dots button { width: 8px; height: 8px; padding: 0; border-radius: 50%; border: 0; background: rgba(255,255,255,.45); transition: width .3s var(--ease-out), background .3s; }
  .dots button[aria-selected="true"] { width: 22px; border-radius: 4px; background: #fff; }
  .feature-info { display: flex; flex-direction: column; padding: 8px 4px; }
  .feature-info .kicker { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--on-tint-faint); margin-bottom: 8px; }
  .feature-info h3 { font: 400 clamp(40px, 4.4vw, 60px)/1 var(--font-display); letter-spacing: -.03em; min-height: 2em; }
  .feature-info hr { border: 0; border-top: 1px solid rgba(255,255,255,.22); margin: 22px 0 18px; }
  .meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .meta small { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--on-tint-muted); margin-bottom: 6px; }
  .meta small svg { width: 15px; height: 15px; }
  .meta strong { font: 400 20px var(--font-display); }
  .feature-info p { font-size: 13px; line-height: 1.55; color: var(--on-tint-muted); margin: 18px 0 22px; max-width: 46ch; }
  .actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: auto; }
  .swap { transition: opacity .35s, transform .35s var(--ease-out); }
  .swap.out { opacity: 0; transform: translateY(6px); }

  /* Recent projects */
  .section-head { display: flex; align-items: baseline; justify-content: space-between; margin: 34px 0 14px; }
  .section-head h2 { font: 400 20px var(--font-display); }
  .section-head a { font-size: 13px; color: var(--on-tint-muted); }
  .section-head a:hover { color: #fff; }
  .recent { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
  .mini { padding: 10px; transition: background .2s, transform .2s var(--ease-out); }
  .mini:hover { background: var(--glass-bg-hover); transform: translateY(-2px); }
  .thumb { aspect-ratio: 16 / 10; border-radius: 12px; margin-bottom: 10px; }
  .mini b { display: block; font-weight: 500; font-size: 14px; padding: 0 4px; }
  .mini span { font-size: 12px; color: var(--on-tint-muted); padding: 0 4px; }

  /* Entrance */
  .rise { opacity: 0; transform: translateY(14px); animation: rise .8s var(--ease-out) forwards; }
  @keyframes rise { to { opacity: 1; transform: none; } }

  /* ---------- Responsive ---------- */
  @media (max-width: 1100px) {
    .grid { grid-template-columns: 1fr; }
    .recent { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .search { width: 180px; }
  }
  @media (max-width: 760px) {
    .panel { margin: 8px; min-height: calc(100dvh - 16px); grid-template-columns: 1fr; border-radius: 22px; }
    .rail { flex-direction: row; justify-content: space-between; padding: 10px 14px; border-right: 0; border-bottom: 1px solid rgba(255,255,255,.10); overflow-x: auto; }
    .logo { margin: 0 6px 0 0; }
    .rail .spacer, .rail .logout { display: none; }
    .me { margin: 0; }
    .nav-btn .tip { display: none; }
    main { padding: 20px 16px 28px; }
    .head h1 { font-size: 28px; }
    .card { padding: 18px; }
    .card-head h2 { font-size: 16px; gap: 6px; }
    .head-actions { margin-left: 0; width: 100%; }
    .search { flex: 1; width: auto; }
    .head-actions .ghost-btn span { display: none; }
    .feature-media { min-height: 230px; }
    .recent { gap: 10px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .blob, .rise { animation: none; }
    .rise { opacity: 1; transform: none; }
    .panel, .art, .swap { transition: none; }
  }
</style>
</head>
<body>
  <div class="aurora" aria-hidden="true"><span class="blob b1"></span><span class="blob b2"></span><span class="blob b3"></span></div>

  <div class="panel" id="panel">
    <!-- ========== Side rail ========== -->
    <nav class="rail" aria-label="Main">
      <a class="logo" href="../home-demo/index.html" aria-label="YourBrand home"></a>
      <a class="nav-btn" href="../home-demo/index.html" aria-label="Create">
        <svg class="i" viewBox="0 0 24 24"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg><span class="tip">Create</span>
      </a>
      <a class="nav-btn" href="#" aria-current="page" aria-label="Overview">
        <svg class="i" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9" rx="2"/><rect x="14" y="3" width="7" height="5" rx="2"/><rect x="14" y="12" width="7" height="9" rx="2"/><rect x="3" y="16" width="7" height="5" rx="2"/></svg><span class="tip">Overview</span>
      </a>
      <a class="nav-btn" href="#" aria-label="Projects">
        <svg class="i" viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg><span class="tip">Projects</span>
      </a>
      <a class="nav-btn" href="#" aria-label="Library">
        <svg class="i" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg><span class="tip">Library</span>
      </a>
      <a class="nav-btn" href="#" aria-label="Templates">
        <svg class="i" viewBox="0 0 24 24"><path d="m12 2 9 5-9 5-9-5z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/></svg><span class="tip">Templates</span>
      </a>
      <a class="nav-btn" href="#" aria-label="Settings">
        <svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg><span class="tip">Settings</span>
      </a>
      <div class="spacer"></div>
      <button class="me" aria-label="Account menu">EB</button>
      <a class="nav-btn logout" href="#" aria-label="Log out">
        <svg class="i" viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg><span class="tip">Log out</span>
      </a>
    </nav>

    <!-- ========== Main ========== -->
    <main>
      <header class="head rise">
        <h1>Overview</h1>
        <div class="chips">
          <span class="chip"><i>🔥</i>7-day streak</span>
          <span class="chip"><i>✓</i>12 projects this month</span>
          <span class="chip"><i>★</i>Pro plan</span>
        </div>
        <div class="head-actions">
          <label class="search">
            <svg class="i" viewBox="0 0 24 24" style="width:15px;height:15px"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
            <input type="search" placeholder="Search projects" aria-label="Search projects">
          </label>
          <button class="ghost-btn" aria-label="Notifications"><svg class="i" viewBox="0 0 24 24"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0"/></svg><span>Alerts</span></button>
          <a class="cream-btn" href="../home-demo/index.html"><svg class="i" viewBox="0 0 24 24" style="width:15px;height:15px"><path d="M12 5v14M5 12h14"/></svg>New</a>
        </div>
      </header>

      <!-- Row 1: activity + profile -->
      <section class="grid">
        <article class="card rise" style="animation-delay:.08s">
          <div class="card-head">
            <h2>Creations <span class="pill" id="totalPill">0</span></h2>
            <h2>Time saved <span class="pill">8hr</span></h2>
          </div>
          <div class="chart-wrap" id="chart" role="img" aria-label="Creations per day this week">
            <div class="tooltip" id="tip"></div>
          </div>
        </article>

        <article class="card profile rise" style="animation-delay:.16s">
          <div class="profile-top">
            <div class="avatar-lg">EB</div>
            <div class="who"><b>Elliot Buglass</b><span>@elliot · Creator</span></div>
            <button class="round-btn" aria-label="Share profile"><svg class="i" viewBox="0 0 24 24" style="width:16px;height:16px"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4"/></svg></button>
          </div>
          <div class="stats3">
            <div><small>Projects</small><strong data-count="80">0</strong></div>
            <div><small>Credits</small><strong data-count="200">0</strong></div>
            <div><small>Shares</small><strong data-count="110">0</strong></div>
          </div>
          <div class="usage">
            <div class="usage-row"><span>Monthly credits</span><span><b>124</b> / 200 used</span></div>
            <div class="bar" role="progressbar" aria-valuenow="62" aria-valuemin="0" aria-valuemax="100" aria-label="Monthly credits used"><span id="usageBar"></span></div>
          </div>
        </article>

        <!-- Row 2: featured project carousel -->
        <div class="feature-media rise" style="animation-delay:.24s" id="media" aria-roledescription="carousel" aria-label="Featured projects">
          <div class="dots" role="tablist" id="dots"></div>
        </div>

        <div class="feature-info rise" style="animation-delay:.32s">
          <div class="swap" id="info">
            <div class="kicker" id="fKicker"></div>
            <h3 id="fTitle"></h3>
            <hr>
            <div class="meta">
              <div><small><svg class="i" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="m21 15-5-5L5 21"/></svg>Assets</small><strong id="fAssets"></strong></div>
              <div><small><svg class="i" viewBox="0 0 24 24"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>Views</small><strong id="fViews"></strong></div>
              <div><small><svg class="i" viewBox="0 0 24 24"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>Edits</small><strong id="fEdits"></strong></div>
            </div>
            <p id="fDesc"></p>
          </div>
          <div class="actions">
            <a class="cream-btn" href="#">Open project</a>
            <button class="glass-btn">Share preview</button>
            <button class="round-btn" id="fav" aria-pressed="false" aria-label="Favourite"><svg class="i" viewBox="0 0 24 24" style="width:16px;height:16px"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8z"/></svg></button>
          </div>
        </div>
      </section>

      <!-- Row 3: recent projects -->
      <div class="section-head rise" style="animation-delay:.4s"><h2>Recent projects</h2><a href="#">See all →</a></div>
      <section class="recent" id="recent"></section>
    </main>
  </div>

<script>
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ================= Data (replace with your API) ================= */
  const WEEK = [
    { day: "Mon", v: 4 }, { day: "Tue", v: 7 }, { day: "Wed", v: 5 }, { day: "Thu", v: 12 },
    { day: "Fri", v: 9 }, { day: "Sat", v: 6 }, { day: "Sun", v: 14 },
  ];
  // Each featured project carries its own panel tint (dark → light) and artwork colours.
  const FEATURED = [
    { kicker: "Featured project", title: "Summer Campaign", assets: "48", views: "12.4k", edits: "36",
      desc: "A warm, sun-soaked launch for the new collection: hero banners, social posts and a short promo video, all generated from one brief.",
      tint: ["#6E2316", "#C8653F"], sky: ["#2B1B2E", "#E8784A", "#F7C08A"], hill: "#3A1F1E" },
    { kicker: "Featured project", title: "Coffee Rebrand", assets: "31", views: "8.9k", edits: "52",
      desc: "Moodboards, a refreshed logo direction and packaging mock-ups for a neighbourhood roastery's new identity.",
      tint: ["#16295E", "#4F7FE0"], sky: ["#0E1838", "#3E6FD8", "#A9C8FF"], hill: "#14204A" },
    { kicker: "Featured project", title: "Product Launch", assets: "64", views: "21.1k", edits: "18",
      desc: "Landing page, announcement email and a week of social content for the app's biggest release yet.",
      tint: ["#4A1752", "#C04FA0"], sky: ["#22102A", "#B24A9E", "#FFB3D9"], hill: "#2A1030" },
  ];
  const RECENT = [
    { title: "Spring lookbook", time: "Edited 2h ago", g: ["#FFB37A", "#FF66F4"] },
    { title: "Podcast cover art", time: "Edited yesterday", g: ["#82BCFF", "#4F88FF"] },
    { title: "Newsletter #14", time: "Edited 3 days ago", g: ["#FF8A7A", "#FE7B02"] },
    { title: "Brand guidelines", time: "Edited last week", g: ["#C9B6FF", "#FF66F4"] },
  ];

  /* ================= Activity chart ================= */
  const chartEl = document.getElementById("chart"), tip = document.getElementById("tip");
  const NS = "http://www.w3.org/2000/svg";
  const total = WEEK.reduce((s, d) => s + d.v, 0);

  function smoothPath(pts) { // Catmull-Rom → cubic Bézier
    let d = `M${pts[0][0]},${pts[0][1]}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
      const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
      d += ` C${c1},${c2},${p2}`;
    }
    return d;
  }

  function drawChart(animate) {
    chartEl.querySelector("svg")?.remove();
    const W = chartEl.clientWidth, H = chartEl.clientHeight, padX = 18, top = 26, bottom = 26;
    const max = Math.max(...WEEK.map(d => d.v));
    const pts = WEEK.map((d, i) => [
      +(padX + i * (W - padX * 2) / (WEEK.length - 1)).toFixed(1),
      +(top + (1 - d.v / max) * (H - top - bottom)).toFixed(1),
    ]);
    const svg = document.createElementNS(NS, "svg");
    const line = smoothPath(pts);
    svg.innerHTML = `
      <defs><linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
      </linearGradient></defs>
      <path class="chart-area" d="${line} L${pts.at(-1)[0]},${H - bottom} L${pts[0][0]},${H - bottom} Z"/>
      <path class="chart-line" d="${line}"/>
      <line class="crosshair" y1="${top - 10}" y2="${H - bottom}"/>`;
    // Dots, direct labels on the peak + latest point only, and day labels
    const maxI = WEEK.findIndex(d => d.v === max);
    pts.forEach(([x, y], i) => {
      svg.insertAdjacentHTML("beforeend", `<circle class="chart-dot" cx="${x}" cy="${y}" r="5"/>`);
      if (i === maxI || i === WEEK.length - 1 || i === 3) svg.insertAdjacentHTML("beforeend", `<text class="chart-label" x="${x}" y="${y - 12}" text-anchor="middle">${WEEK[i].v}</text>`);
      svg.insertAdjacentHTML("beforeend", `<text class="chart-x" x="${x}" y="${H - 6}" text-anchor="middle">${WEEK[i].day}</text>`);
    });
    chartEl.prepend(svg);

    if (animate && !reduced) {
      const path = svg.querySelector(".chart-line"), len = path.getTotalLength();
      path.style.strokeDasharray = len; path.style.strokeDashoffset = len;
      path.getBoundingClientRect();
      path.style.transition = "stroke-dashoffset 1.4s cubic-bezier(.22,1,.36,1) .3s";
      path.style.strokeDashoffset = 0;
    }

    // Hover: nearest day → crosshair + tooltip
    const cross = svg.querySelector(".crosshair");
    chartEl.onpointermove = e => {
      const x = e.clientX - chartEl.getBoundingClientRect().left;
      let i = 0; pts.forEach((p, j) => { if (Math.abs(p[0] - x) < Math.abs(pts[i][0] - x)) i = j; });
      cross.setAttribute("x1", pts[i][0]); cross.setAttribute("x2", pts[i][0]); cross.style.opacity = 1;
      tip.innerHTML = `${WEEK[i].day} · <b>${WEEK[i].v}</b> creations`;
      tip.style.left = pts[i][0] + "px"; tip.style.top = pts[i][1] + "px"; tip.style.opacity = 1;
    };
    chartEl.onpointerleave = () => { cross.style.opacity = 0; tip.style.opacity = 0; };
  }
  drawChart(true);
  let rT; addEventListener("resize", () => { clearTimeout(rT); rT = setTimeout(() => drawChart(false), 120); });

  /* ================= Count-up numbers ================= */
  function countUp(el, to) {
    if (reduced) { el.textContent = to; return; }
    const t0 = performance.now(), dur = 1200;
    (function f(t) { const p = Math.min(1, (t - t0) / dur); el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))); if (p < 1) requestAnimationFrame(f); })(t0);
  }
  document.querySelectorAll("[data-count]").forEach(el => countUp(el, +el.dataset.count));
  countUp(document.getElementById("totalPill"), total);
  requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById("usageBar").style.width = "62%"));

  /* ================= Featured carousel ================= */
  const media = document.getElementById("media"), dots = document.getElementById("dots"), panel = document.getElementById("panel");
  const info = document.getElementById("info");
  const artSVG = f => `
    <svg viewBox="0 0 800 450" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id="s${f.title.length}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="${f.sky[0]}"/><stop offset=".55" stop-color="${f.sky[1]}"/><stop offset=".72" stop-color="${f.sky[2]}"/>
        </linearGradient>
        <radialGradient id="sun${f.title.length}" cx=".62" cy=".6" r=".35"><stop offset="0" stop-color="#fff" stop-opacity=".75"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
        <linearGradient id="w${f.title.length}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${f.sky[2]}" stop-opacity=".9"/><stop offset="1" stop-color="${f.hill}"/></linearGradient>
      </defs>
      <rect width="800" height="450" fill="url(#s${f.title.length})"/>
      <rect width="800" height="450" fill="url(#sun${f.title.length})"/>
      <path d="M0 300 L140 250 L230 200 L300 150 L360 175 L420 120 L480 160 L560 210 L660 240 L800 270 L800 320 L0 320Z" fill="${f.hill}" opacity=".95"/>
      <path d="M0 320 L800 320 L800 450 L0 450Z" fill="url(#w${f.title.length})"/>
      <path d="M0 320 C200 360 420 300 800 350 L800 450 L0 450Z" fill="${f.hill}" opacity=".55"/>
    </svg>`;
  FEATURED.forEach((f, i) => {
    media.insertAdjacentHTML("afterbegin", `<div class="art" data-i="${i}">${artSVG(f)}</div>`);
    const b = document.createElement("button");
    b.setAttribute("role", "tab"); b.setAttribute("aria-label", f.title);
    b.onclick = () => { show(i); stopAuto(); };
    dots.append(b);
  });

  let current = -1, auto;
  function show(i) {
    if (i === current) return;
    current = i;
    const f = FEATURED[i];
    media.querySelectorAll(".art").forEach(a => a.classList.toggle("on", +a.dataset.i === i));
    [...dots.children].forEach((b, j) => b.setAttribute("aria-selected", j === i));
    panel.style.setProperty("--tint-a", f.tint[0]);
    panel.style.setProperty("--tint-b", f.tint[1]);
    info.classList.add("out");
    setTimeout(() => {
      fKicker.textContent = f.kicker; fTitle.textContent = f.title;
      fAssets.textContent = f.assets; fViews.textContent = f.views; fEdits.textContent = f.edits; fDesc.textContent = f.desc;
      info.classList.remove("out");
    }, reduced ? 0 : 300);
  }
  const startAuto = () => { if (!reduced) auto = setInterval(() => show((current + 1) % FEATURED.length), 7000); };
  const stopAuto = () => clearInterval(auto);
  media.addEventListener("pointerenter", stopAuto);
  media.addEventListener("pointerleave", () => { stopAuto(); startAuto(); });
  show(0); startAuto();

  document.getElementById("fav").onclick = e => {
    const b = e.currentTarget; b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") !== "true");
  };

  /* ================= Recent projects ================= */
  document.getElementById("recent").innerHTML = RECENT.map((p, i) => `
    <a class="card mini rise" href="#" style="animation-delay:${.45 + i * .06}s">
      <div class="thumb" style="background: radial-gradient(70% 70% at 30% 30%, rgba(255,255,255,.55), transparent 60%), linear-gradient(135deg, ${p.g[0]}, ${p.g[1]})"></div>
      <b>${p.title}</b><span>${p.time}</span>
    </a>`).join("");

  /* ================= Mouse spotlight on the panel ================= */
  if (!reduced && matchMedia("(pointer: fine)").matches) {
    let raf;
    panel.addEventListener("pointermove", e => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const r = panel.getBoundingClientRect();
        panel.style.setProperty("--mx", e.clientX - r.left + "px");
        panel.style.setProperty("--my", e.clientY - r.top + "px");
      });
    });
  }
</script>
</body>
</html>
````
