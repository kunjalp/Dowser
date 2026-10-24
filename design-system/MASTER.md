# Dowser Design System: MASTER

The main reference for how Dowser looks. It builds on the tokens already in
`app/src/app/globals.css` and does not replace them. Page-specific overrides go
in `design-system/pages/<page>.md` if any are added later.

**Product.** A dark, map-first operations dashboard for state oil-well plugging
staff (desktop), a phone **Field View** for crews, and a projector demo for judges.

**Style.** Flat, square, dense, Swiss/utilitarian. Keep everything that makes it look this way today:
- `border-radius: 0` everywhere (map point symbols are the only round shapes)
- 1px hairline dividers, no shadows, no gradients
- small uppercase letter-spaced labels
- monospace for every data value (IDs, scores, readings, distances, dates)
- system font stacks only, no web fonts (works offline in the field, no layout shift)

**How it was made.** The `ui-ux-pro-max` design-system search suggested
"Minimalism & Swiss Style" for dashboards and professional tools, and "blue data + amber
highlights". Both match what Dowser already does. Its light-mode palette, Fira fonts
and scroll-reveal motion do not fit a dark map tool and were left out. The UX
rules used here are `color-not-only`, `color-accessible-pairs`,
`color-dark-mode`, `touch-target-size`, `readable-font-size`, `focus-states`.
Every contrast ratio below was computed with the WCAG 2.x relative-luminance
formula, not estimated.

---

## 1. Color tokens

### 1.1 Surfaces and lines (existing values, kept)

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0a0d10` | Page and map-area background, inputs inside panels |
| `--panel` | `#0f1215` | Sidebar, detail panel, map controls, field rows |
| `--panel-2` | `#14181c` | Hover and selected rows, nested blocks (priority box, sparkline, inputs) |
| `--line` | `#2a3036` | Decorative dividers between rows and sections |
| `--line-strong` | `#3a424a` → **`#626b74`** | Borders on **interactive controls** (checkbox, input, chip, select). Must reach 3:1, see §2.3 |
| `--line-subtle` *(new)* | `#3a424a` | The old `--line-strong` value, kept for non-interactive emphasis (ramp outline, gauge track, tags) |

`--panel` and `--bg` differ by only 1.04:1, and a projector will wash that out
completely. **Never use a surface change alone to separate regions. Always add a
1px `--line` border.** The CSS already does this everywhere, so keep it that way.

### 1.2 Text

| Token | Value | Use |
|---|---|---|
| `--text` | `#dfe4e8` | Body text, values |
| `--muted` | `#8a949e` → **`#9aa4ae`** | Secondary labels, captions, section headers. Lightened for projector margin (6.3 → 7.7:1 on `--bg`) |
| `--on-accent` | `#0f1215` | Text on any solid status, accent or sim fill |
| `--on-sim` *(new)* | `#0a0d10` | Text on the simulated-data banner |

### 1.3 Interaction accent (existing, meaning narrowed)

| Token | Value | Use |
|---|---|---|
| `--accent` | `#f59e0b` | **Interaction only:** focus outlines, selected-row left bar, primary buttons (Navigate, Undo), active slider thumb, `.link-btn`, gauge threshold mark |

### 1.4 Status tokens (new, named)

These replace the hex values hard-coded in `STATUS_META` (`app/src/lib/types.ts`).
The TS file should read the CSS variables or mirror these values exactly. MapLibre
paint properties can't read CSS variables, so keep one shared constant and
reference it from both places.

| Status | Token | Current | **Proposed** | Hue | Non-color cue (required) |
|---|---|---|---|---|---|
| Confirmed leaking | `--status-leaking` | `#e5484d` | **`#f0565b`** | red | Text label "LEAKING", filled square marker, red row tint + left bar |
| Queued | `--status-queued` | `#4a9fd4` | **`#5aaee3`** | blue | Label "QUEUED", ring marker with center dot |
| Candidate | `--status-candidate` | `#f59e0b` | *score ramp* (below) | amber ramp | Score number next to every dot; label "CANDIDATE" |
| Not leaking | `--status-clear` | `#3fa76a` | **`#4cbc7a`** | green | Label "NOT LEAKING", hollow marker |
| No well | `--status-nowell` | `#8b929a` | **`#959ca4`** | gray | Label "NO WELL", small hollow marker at reduced opacity |
| Mislocated | `--status-mislocated` | `#9a85d4` | **`#a893e0`** | violet | Label "MISLOCATED", marker plus an offset line to the corrected position if one exists |

**Candidate score ramp** (existing `SCORE_RAMP`, kept): `--score-lo #fde68a`,
`--score-mid #f59e0b`, `--score-hi #b45309`. A candidate's color *is* its score.

The proposed values are each lifted 5–10% in lightness. That follows the skill's
`color-dark-mode` rule (desaturated, lighter tones on dark backgrounds) and makes
every status pass AA as *text* on all three surfaces and as the *fill* behind
`--on-accent` badge text (§2).

**Red vs green.** Leaking (L≈0.27) and not-leaking (L≈0.40) differ in lightness
as well as hue, so they still read as different for red/green color-blind
viewers. The text label is still required: every status chip, badge and legend
row must carry its word, never just a swatch (`color-not-only`).

### 1.5 Resolving the accent vs. amber-status clash

**What the code actually does:** `STATUS_META` makes **candidate** amber
(`#f59e0b`, the same value as `--accent`). **Queued** is already blue
(`#4a9fd4`). So the real clash is accent vs. *candidate* (and the score ramp,
whose midpoint is exactly `--accent`), not accent vs. queued.

**Decision:**

1. **Queued is never amber.** It stays blue (`--status-queued #5aaee3`). Queued
   is a workflow state ("we've committed to visit"), not an alert, so a calm
   hue fits.
2. **Amber means "needs attention / act here".** Candidates are unresolved and
   score-ranked, and the accent marks what you are acting on. Sharing the
   amber *family* is deliberate, but the two never share a *shape*:
   - **Status amber = filled shapes:** dots, ramp, badge fills.
   - **Accent amber = edges and buttons:** 2px left bar, 1px focus outline,
     solid action buttons with uppercase text.
3. **Selection on the map is never amber.** A selected point gets the
   existing white ring (`.dot.ring`, `#fff`, 1.5px), so a selected
   high-score candidate stays distinguishable from its neighbours.
4. **The candidate badge** renders as `CANDIDATE · 0.82`, with the score always
   shown, so an amber badge is never confused with an amber button.
   Action buttons (`.action`, `.field-btn`) keep their uppercase verb label.
5. The `.sim` amber pill is replaced by the dedicated sim treatment (§5), so
   amber no longer means "simulated" anywhere.

### 1.6 Other fixed colors to turn into tokens

These literal values currently sit in `globals.css`. Give them names:

| Literal | Token | Use |
|---|---|---|
| `#e5484d` (leak row, gauge `.hi`, `.rank em.down`) | `--status-leaking` | |
| `#3fa76a` (toast, live dot, `.rank em.up`) | `--ok` → same value as `--status-clear` | Success and "live" (not a status, but the same hue family) |
| `#ef6a6e` (`.field-error`) | `--danger-text` `#ef6a6e` | Form and network errors (6.45:1 on `--bg`) |
| `#0f1215` in `color-mix(... , #0f1215)` | `var(--panel)` | Mix base |
| `#0009` dot outline | `--dot-outline: #0009` | Map and list markers |

---

## 2. WCAG AA contrast check

AA thresholds: **4.5:1** for normal text, **3:1** for large text (≥24px, or
≥18.66px bold) and for UI component boundaries (1.4.11). Dowser's labels are
10–13px, so **everything is treated as normal text (4.5:1).**

### 2.1 Text tokens on surfaces

| Foreground | on `--bg` | on `--panel` | on `--panel-2` | Verdict |
|---|---|---|---|---|
| `--text` `#dfe4e8` | 15.21 | 14.67 | 13.93 | AAA |
| `--muted` current `#8a949e` | 6.32 | 6.09 | 5.79 | AA |
| `--muted` proposed `#9aa4ae` | 7.70 | 7.42 | 7.05 | AAA (better on a projector) |
| `--accent` `#f59e0b` | 9.07 | 8.75 | 8.31 | AAA |
| `--danger-text` `#ef6a6e` | 6.45 | 6.22 | 5.91 | AA |
| `--line` `#2a3036` | 1.46 | 1.41 | 1.34 | Decorative only, never for text |
| `--line-strong` current `#3a424a` | 1.91 | 1.84 | 1.75 | **Fails 1.4.11 as a control border** |

### 2.2 Status colors as text

| Status | Current on bg / panel / panel-2 | Proposed on bg / panel / panel-2 |
|---|---|---|
| Leaking | 4.98 / 4.80 / 4.56 (barely passes) | **5.74 / 5.54 / 5.26** |
| Queued | 6.68 / 6.44 / 6.12 | 7.98 / 7.69 / 7.30 |
| Candidate (amber) | 9.07 / 8.75 / 8.31 | unchanged |
| Not leaking | 6.44 / 6.22 / 5.90 | 8.15 / 7.86 / 7.46 |
| No well | 6.19 / 5.97 / 5.67 | 7.02 / 6.77 / 6.43 |
| Mislocated | 6.20 / 5.98 / 5.67 | 7.34 / 7.08 / 6.72 |

### 2.3 Badge and chip fills (`--on-accent` text on the status fill)

Today `.badge`, `.chip.on` and `.action:hover` darken the fill with
`color-mix(in srgb, var(--c) 88%, #0f1215)`:

| Status | Current 88% mix | Ratio | Proposed **solid** fill | Ratio |
|---|---|---|---|---|
| Leaking | `#cb4246` | **3.94 ✗ fails AA** | `#f0565b` | **5.54 ✓** |
| Queued | `#438ebd` | 5.23 | `#5aaee3` | 7.69 ✓ |
| Candidate | `#d98d0c` | 6.95 | `#f59e0b` | 8.75 ✓ |
| Not leaking | `#399560` | 5.05 | `#4cbc7a` | 7.86 ✓ |
| No well | `#7c838a` | 4.89 | `#959ca4` | 6.77 ✓ |
| Mislocated | `#8977bd` | 4.86 | `#a893e0` | 7.08 ✓ |

**The most important thing on screen, the "CONFIRMED LEAKING" badge, fails AA
today.** The fix is to drop the 88% darkening and use solid status fills
(`background: var(--c)`).

### 2.4 Other pairs checked

| Pair | Ratio | |
|---|---|---|
| `--on-accent` on `--accent` (Navigate, Undo, `.sim` today) | 8.75 | ✓ |
| `--text` on leak-row tint (`--status-leaking` 12% over `--panel`) | 13.21 | ✓ |
| `--muted` on leak-row tint | 5.48 | ✓ |
| `--on-sim` on `--sim` (§5) | 17.67 | ✓ |
| Control border `#626b74` on `--bg` / `--panel-2` | 3.59 / 3.29 | ✓ 1.4.11 |
| Score ramp high `#b45309` dot on `--bg` | 3.88 | ✓ (non-text, needs 3:1) |

---

## 3. Type scale

### 3.1 Rationale

Today the base is 13px and labels go down to 9–10px (`.tag` 9px, `.rank em`
9px, chips, badges and map-control headers 10px). On a projector, 1px of
CSS can render as a blurred sub-pixel, and judges sit 4–8m away. The
skill's `readable-font-size` rule asks for 16px body text on mobile.

**Decision:**
- **Desktop base 13 → 14px.** One step up. It keeps density (a 380px sidebar
  still fits ~12 rows on a 900px screen) and helps on laptops and projectors.
- **Floor of 11px.** Nothing in the UI goes below 11px. That removes the 9px and 10px sizes.
- **Field View base 16px.** Prevents iOS zoom-on-focus in the search and note
  inputs and suits outdoor glare.
- **Presentation mode.** A `.present` class on `<html>` (toggled by a `?present`
  query param or a keyboard shortcut) multiplies the whole scale by **1.25**.
  Use it for the judges' projector instead of browser zoom, which breaks
  the 380px grid and MapLibre's canvas sizing.

### 3.2 Tokens

| Token | Desktop | `.present` | Field View | Used for (current → new) |
|---|---|---|---|---|
| `--fs-2xs` | 11px | 14px | 12px | Tags, rank delta, legend ramp labels, figcaptions (were 9–10px) |
| `--fs-xs` | 12px | 15px | 13px | Chips, badges, section headers (h3), map-control headers, `.small` (were 10–11px) |
| `--fs-sm` | 13px | 16px | 14px | Row titles, facts, part labels, slider labels (were 12px) |
| `--fs-base` | **14px** | 18px | **16px** | Body (was 13px) |
| `--fs-md` | 16px | 20px | 18px | Detail-panel h2, sidebar h1 (were 13–14px) |
| `--fs-lg` | 20px | 25px | 20px | Field paired-well heading, field distance |
| `--fs-display` | 56px | 72px | 56px | Live sensor reading `.reading-value` |

**Line height:** `--lh-tight: 1.2` (data rows, labels), `--lh-base: 1.4` (body,
briefs). **Weights:** 400 body, 600 labels and badges, 700 headings, values and
buttons. **Letter-spacing on uppercase labels:** `0.06em` for chips and badges,
`0.10em` for section headers, `0.14em` for the app title. Keep these as they are.

**Families:** `--sans` for prose and labels. `--mono` for **every number, ID,
score, distance, timestamp and reading**. Keep `font-variant-numeric:
tabular-nums` on `body` so columns line up.

---

## 4. Spacing and borders

### 4.1 Spacing: 4px grid with a 2px half-step for dense rows

| Token | Value | Use |
|---|---|---|
| `--sp-0` | 2px | Inside badges and tags, chip row gaps in dense lists |
| `--sp-1` | 4px | Chip gap, label-to-value gap, bar-to-text |
| `--sp-2` | 8px | Grid gaps, section internal spacing, row vertical padding (desktop) |
| `--sp-3` | 12px | Panel side padding (sidebar, detail), row horizontal padding |
| `--sp-4` | 16px | Field View side padding, empty-state padding |
| `--sp-6` | 24px | Space between major blocks in the Field View |

The current CSS uses 2/3/4/6/8/10/12/14/16. Collapse to the tokens above:
3→4, 6→8 or 4 (pick per context), 10→8 or 12, 14→12 or 16.

**Touch targets:**
- Desktop: ≥ 32px row height (mouse).
- Field View: **≥ 56px** for rows, inputs and photo; **≥ 64px** for primary
  Leak / No-leak buttons and Undo; **≥ 44px** for chips (already true, meets
  `touch-target-size`); ≥ 8px between adjacent targets.
- `.present`: hit areas grow with the scale, nothing extra needed.

### 4.2 Borders

| Rule | Value |
|---|---|
| Radius | `0` everywhere. **Exceptions:** map point symbols and their legend swatches (`.legend .dot`) stay round so the legend matches the map |
| Decorative divider | `1px solid var(--line)` |
| Interactive control boundary | `1px solid var(--line-strong)` (`#626b74`, 3:1) for checkbox, input, select, chip-off |
| Non-interactive emphasis | `1px solid var(--line-subtle)` for ramp, gauge track, tag, dashed photo slot |
| Selection | `2px` left bar in `--accent` (list row, field row) |
| Status emphasis | `2px` left bar in the status color (leak row); selection overrides it |
| Primary field controls | `2px solid var(--c)` |
| Focus | `outline: 2px solid var(--accent); outline-offset: 1px` (currently 1px; 2px meets `focus-states` and survives a projector). Apply to **all** focusable elements including `a`, `input[type=range]`, `.row`, `.field-row` |
| Shadows | None. Floating panels are separated by a border, not elevation |
| Simulated data | `2px dashed var(--sim)`, used only for sim (§5) |

### 4.3 Motion

Keep it minimal: 0.2s ease for the detail panel slide and zoom-slider shift, 0.4s
for the rank-change row flash. Add
`@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }`.

---

## 5. "SIMULATED SENSOR DATA" treatment

**Problem today:**
- The map banner is `--panel-2` with an amber 3px left edge and 11px text. It
  blends in and looks like regular chrome.
- The detail-panel `.sim` and field `.sim` pills are amber, the same color as
  candidate and accent.
- A judge glancing at a projected screen will not notice either.

**Goal:** no one can see a sensor value without also seeing that it is
simulated. Achieve that with **color, pattern, size and placement**, and use no
hue that already means something.

### 5.1 Tokens

```css
--sim:        #f2f4f6;  /* near-white: no status or accent uses it */
--on-sim:     #0a0d10;  /* 17.67:1 */
--sim-stripe: repeating-linear-gradient(-45deg, var(--on-sim) 0 8px, var(--sim) 8px 16px);
```

Near-white is the brightest thing in a dark UI, so it is visible from the back of a
room and on any projector. It belongs to no status, so it can't be misread as
leaking, candidate or anything else. The diagonal hazard stripe reads as
"warning / test" without depending on color.

### 5.2 Map-wide banner (`.demo-banner`)

```
▨▨▨▨│ SIMULATED SENSOR DATA — NOT FIELD READINGS │▨▨▨▨
```

- Full width across the top of the map area. Height **32px** desktop, **40px** in `.present`.
- Background `--sim`, text `--on-sim`, `700 var(--fs-sm) var(--mono)`,
  uppercase, `letter-spacing: 0.12em`, centered.
- **24px hazard-stripe blocks at each end** (`background: var(--sim-stripe)`).
- `border-bottom: 2px solid var(--on-sim)`.
- `role="status"` (already present). Never dismissible while any sim data
  is on screen.
- Panels below shift down to clear it: `.map-control { top: 42px }`, `.detail { top: 32px }`.
  These offsets already exist, update the numbers.
- On mobile (≤800px), keep the size. Shorten the text to "SIMULATED DATA" rather
  than shrinking it.

### 5.3 On the data itself (detail panel and field reading card)

The banner alone isn't enough. A screenshot of the detail panel or the field
reading card must still show the data is fake.

- **Header strip** above the sparkline / reading: full width of the section,
  `--sim` background, hazard-stripe left edge (12px), text "SIMULATED SENSOR DATA",
  `700 var(--fs-xs) var(--mono)`, 24px tall (Field View: 32px). Replaces `.sim`.
- **The data container itself** (`.spark`, `.reading-card`, `.gauge`) gets
  `border: 2px dashed var(--sim)`. Dashed borders are used **only** for sim.
- **Reading value** (`.reading-value`) gets a trailing `SIM` tag at `--fs-xs` in
  the same `--sim` fill, so the 56px number is never seen without it.
- **Field list rows** that show `· sim` today get a proper `.tag.sim` (solid
  `--sim`, `--on-sim` text) instead of muted inline text.

---

## 6. Proposed changes to `globals.css`, in priority order

Each item can ship on its own. P0 items fix accessibility or demo-critical problems.

### P0: must fix before the demo

1. **Leaking badge contrast.** In `.badge`, `.chip.on`, `.action:hover` and
   `.field-btn:active`, replace `color-mix(in srgb, var(--c) 88%, #0f1215)` with
   `var(--c)`, and set `--status-leaking: #f0565b`. Fixes the 3.94:1 failure on
   the most important label.
2. **Simulated-data treatment.** Add the `--sim`, `--on-sim` and `--sim-stripe`
   tokens. Restyle `.demo-banner` per §5.2 and replace `.sim` with the §5.3 strip.
   Add `.sim-data { border: 2px dashed var(--sim) }`. *(Requires small JSX
   changes in `page.tsx`, `DetailPanel.tsx` and `field/page.tsx` to apply the classes.)*
3. **Named status tokens.** Add `--status-leaking/queued/clear/nowell/mislocated`
   and `--score-lo/mid/hi` to `:root`. Replace the literal `#e5484d` and `#3fa76a`
   values in `.row.leak`, `.reading-card.leak`, `.gauge-fill.hi`, `.rank em.*`,
   `.live-dot.on` and `.field-toast`. Mirror the values in `STATUS_META`.
4. **Projector type floor.** Add the `--fs-*` tokens. Set the `body` base to
   `var(--fs-base)` (14px). Raise every 9px and 10px declaration to `--fs-2xs` or
   `--fs-xs` (`.tag`, `.rank em`, `.chip`, `.badge`, `.sim`, `.map-control::before`,
   `.legend::before`, `.ramp-labels`, `.evidence figcaption`, `.detail-body h3`,
   `.priority-head`, `.reading-top`, `.gauge-legend`).

### P1: high value

5. **Presentation mode.** Add a `:root.present { --fs-...: ... }` block with the
   1.25× values. Widen `.shell` columns to `440px 1fr` and `.detail` to `460px`
   in present mode. *(Needs a one-line toggle in `layout.tsx` or `page.tsx`.)*
6. **Control border contrast.** Set `--line-strong: #626b74`. Add
   `--line-subtle: #3a424a` and point `.ramp`, `.gauge`, `.tag` and `.field-photo` at it.
7. **Focus ring 2px** and extend it to `a:focus-visible`,
   `input:focus-visible` (range, text) and `.row:focus-visible`. Today only
   checkbox, button and select get one.
8. **Field View base 16px.** Add `.field { font-size: var(--fs-base-field, 16px) }`
   and make sure `.field-search` and `.field-note` inherit ≥16px (stops iOS zoom).
9. **Lighten `--muted`** to `#9aa4ae`.

### P2: consistency and cleanup

10. **Spacing tokens** (`--sp-0..6`). Replace the 3/6/10/14px paddings per §4.1.
11. **Tokenize the remaining literals:** `--danger-text`, `--ok`, `--dot-outline`,
    and `var(--panel)` as the `color-mix` base.
12. **Candidate badge text** shows the score (`CANDIDATE · 0.82`). *(JSX change.)*
13. **Reduced motion** media query (§4.3).
14. **Remove the duplicate `.sim` rule** (lines 114 and 180 conflict on
    `margin`) once item 2 lands.
15. **Separate the `.field` padding declarations.** The safe-area padding block
    overrides the earlier `.field` padding. Merge them into one rule.

---

## Pre-delivery checklist (Dowser-specific)

- [ ] Every status shows a **text label** next to its color (chips, badges, legend, field rows)
- [ ] No text below 11px (desktop) or 12px (field)
- [ ] All status fills pass 4.5:1 with `--on-accent` text (run the §2 check after changing any hex)
- [ ] Control borders pass 3:1 against their surface
- [ ] Every focusable element shows a 2px amber outline
- [ ] No amber in any meaning other than candidate/score (fills) or interaction (edges and buttons)
- [ ] Simulated data shows the banner **and** a per-panel strip **and** a dashed border
- [ ] Field View targets ≥ 56px (primary ≥ 64px), inputs ≥ 16px text
- [ ] `.present` mode checked on a real projector or at 1280×720 from 4m away
- [ ] `border-radius: 0` everywhere except round map points and their legend swatches
