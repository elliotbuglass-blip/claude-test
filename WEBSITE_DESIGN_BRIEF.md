# Build brief: signed-in home page, "Let's get creative"

> **For the coding agent:** this brief describes one page: the home screen users land on **after signing in** to the platform. It is styled after the hero of lovable.dev: a warm off-white page, a soft animated colour gradient (blue, pink, red, orange) glowing up from the bottom, and an AI chat box in the centre.
>
> A finished, working reference lives at **`home-demo/index.html`**. It is plain HTML/CSS/JS with no dependencies. Port it into this project's stack rather than designing from scratch. Ignore `FRAMER_STYLE_README.md` and `hero-demo/` if present; they were earlier explorations of a dark style and do not apply.
>
> Use lovable.dev as a style reference only. Do not copy its logo, wording, images or code.

---

## 1. What the page is

A full-screen, single-purpose launch pad:

```
┌───────────────────────────────────────────────────────────┐
│ [logo] YourBrand                [My projects] [Upgrade] (EB) │  ← transparent top bar
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
4. **Wire up for real:** the chat box must submit to the app's real create/chat endpoint or route (see §6). The avatar opens the existing account menu. "My projects" goes to the existing projects list. "Upgrade" goes to the existing billing page; hide it for paid users.
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
- **Right:** an outlined "My projects" button (1px `--color-border`, radius 8px), a dark "Upgrade" button (`#1C1C1C`, white text, `--shadow-button`), and a round 32px avatar with the user's initials or photo that opens the account menu.
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
| My projects / Upgrade / Avatar | Link to the existing projects page, billing page and account menu. |
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
- [ ] The placeholder types through examples and stops on focus.
- [ ] Textarea auto-grows; Enter sends and Shift+Enter adds a new line; send is disabled until there's text.
- [ ] Submitting calls the real backend and routes to the result; loading and error states exist.
- [ ] Chips fill the box without sending.
- [ ] All buttons have accessible labels and visible focus; contrast meets WCAG AA.
- [ ] Checked at 375px, 768px and 1440px; no horizontal scroll.
- [ ] Lighthouse: Performance ≥ 90, Accessibility ≥ 95, CLS < 0.1.
