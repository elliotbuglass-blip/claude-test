# Build brief: signed-in app, Home ("Let's get creative") + Overview dashboard

> **For the coding agent:** this brief describes two pages that users see **after signing in**:
>
> - **Part 1, Home (`/`):** "Let's get creative". A warm off-white page with a soft animated colour gradient (blue, pink, red, orange) glowing up from the bottom and an AI chat box in the centre. Styled after the hero of lovable.dev.
> - **Part 2, Overview (`/overview`):** a dashboard where everything sits inside one large rounded panel tinted in a rich colour taken from the same gradient family, with frosted-glass cards, an icon side rail, an activity chart, a profile card, a featured-project carousel and recent projects.
>
> Both pages share the same tokens, fonts and gradient colours, so they feel like one product. Finished, working references for both pages are included (see the appendices, or `home-demo/index.html` and `dashboard-demo/index.html`). They are plain HTML/CSS/JS with no dependencies. Port them into this project's stack rather than designing from scratch. Ignore `FRAMER_STYLE_README.md` and `hero-demo/` if present; they were earlier explorations of a dark style and do not apply.
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
