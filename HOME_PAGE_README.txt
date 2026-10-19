# Build brief: signed-in home page, "Let's get creative"

> **For the coding agent:** this brief describes one page: the home screen users land on **after signing in** to the platform. It is styled after the hero of lovable.dev: a warm off-white page, a soft animated colour gradient (blue, pink, red, orange) glowing up from the bottom, and an AI chat box in the centre.
>
> A finished, working reference is included in full in **Appendix A** at the bottom of this file. It is plain HTML/CSS/JS with no dependencies. Port it into this project's stack rather than designing from scratch. If you want to preview it first, save Appendix A as `index.html` and open it in a browser.
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
- [ ] With a mouse, the glow smoothly trails the cursor anywhere on the page and the aurora shifts subtly the other way; it's off for touch and reduced motion, with no dropped frames.
- [ ] The placeholder types through examples and stops on focus.
- [ ] Textarea auto-grows; Enter sends and Shift+Enter adds a new line; send is disabled until there's text.
- [ ] Submitting calls the real backend and routes to the result; loading and error states exist.
- [ ] Chips fill the box without sending.
- [ ] All buttons have accessible labels and visible focus; contrast meets WCAG AA.
- [ ] Checked at 375px, 768px and 1440px; no horizontal scroll.
- [ ] Lighthouse: Performance ≥ 90, Accessibility ≥ 95, CLS < 0.1.

---

## Appendix A: complete reference implementation (`index.html`)

This is the full working page: plain HTML/CSS/JS with no build step. Everything in this brief is implemented here. Port it into the app's framework, replacing "YourBrand", the "EB" initials, the example prompts and chips, and the submit handler (currently just `console.log`) with real data and API calls.

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
      <button class="btn btn-ghost nav-hide-sm">My projects</button>
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
