# Design

The page borrows the language of Elliot's Aston Martin deck: white ground,
hairline rules instead of cards, oversized grotesque numerals, letterspaced
uppercase eyebrows. Monochrome, with a single red reserved for overdue state.

If a change makes it look more like a generic analytics dashboard — rounded
cards, drop shadows, a colour per metric, gradients — it is wrong.

## Tokens

Defined on `:root`, redefined for dark under both
`@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`
and `:root[data-theme="dark"]`.

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#ffffff` | `#0b0b0c` |
| `--surface-2` | `#f5f5f4` | `#161617` |
| `--line` | `#e4e3e1` | `#262627` |
| `--rule` | `#0d0d0d` | `#f2f1ef` |
| `--fg` | `#0d0d0d` | `#f2f1ef` |
| `--muted` | `#767674` | `#8b8b89` |
| `--ink-soft` | `#d8d7d4` | `#2e2e30` |
| `--ink-mid` | `#a8a7a4` | `#5c5c5f` |
| `--alert` | `#a8201a` | `#e8695f` |

`--line` is for hairlines between tiles and rows. `--rule` is the heavier
section underline and button borders. `--ink-soft` fills chart areas and the
projection band. `--alert` is overdue state only — never a chart series,
never a general accent.

## Type

**Archivo**, weights 400–800, from Google Fonts. Fallbacks Helvetica, Arial,
system-ui.

| Role | Spec |
|---|---|
| Body | 15px / 1.5, `letter-spacing: -0.004em` |
| `h1` | 21px, 800, uppercase, `-0.02em` |
| Eyebrow | 10px, 600, uppercase, `letter-spacing: .16em`, muted |
| Nav tab | 11px, 600, uppercase, `.13em` |
| Hero numeral | `clamp(54px, 12vw, 104px)`, 800, line-height .88, `-0.045em` |
| Tile value | 34px, 800, `-0.035em` |
| Row numeral | 25px, 800, `-0.035em` |
| Button | 11px, 600, uppercase, `.11em` |

Every numeral uses `font-variant-numeric: tabular-nums`. Figures change on
reload and must not shift the layout.

## Number formatting

`fmt()`:

- ≥ 10,000,000 → one decimal, e.g. `10.2M`
- ≥ 1,000,000 → two decimals, trailing zeros stripped, e.g. `4.29M`
- ≥ 10,000 → rounded thousands, e.g. `30k`
- below that → `toLocaleString("en-GB")`
- null / NaN → an em dash

Dates are `en-GB` throughout. Day before month, everywhere, no exceptions.

## Layout

- `max-width: 1080px`, 24px side gutter, 16px below 520px
- Sticky header respecting `env(safe-area-inset-top)`
- Tiles: `repeat(auto-fit, minmax(152px, 1fr))`, hairline borders, right border
  dropped on the last tile and on all tiles below 620px
- Sections separated by a `--rule` underline under the eyebrow, not by boxes

## Charts

Hand-written inline SVG. No charting library — do not add one.

- `viewBox` with `width: 100%; height: auto` so they scale
- Two gridlines on small charts, three on the projection
- `niceTop()` rounds the axis maximum to a sensible value
- Hover finds the nearest x and positions a tooltip as a percentage of the
  viewBox, so it tracks correctly at any width
- Touch supported via `touchmove` (passive) and `touchend`

## Motion and accessibility

- Loading skeletons pulse at 1.6s; `prefers-reduced-motion: reduce` disables
  all animation and transitions
- Focus rings: `2px solid var(--fg)`, `outline-offset: 3px`
- Charts carry `role="img"` and an `aria-label`
- React escapes interpolated strings automatically, so the prototype's `esc()`
  is not needed for normal rendering. It **is** still needed anywhere a chart
  builds SVG as a string — carry it over for those paths, and never use
  `dangerouslySetInnerHTML` with email content or captions.
