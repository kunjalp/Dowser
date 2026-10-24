# UI Requests

Changes that came out of the P0 pass in `design-system/MASTER.md` §6 but
were kept out of it because they touch `.tsx`, `app/src/lib/`, or layout. Only
`app/src/app/globals.css` was edited in that pass.

Each request lists the file, the exact change, and why. The CSS for every
request below is already in place, so the request only has to supply the class
name, value or markup.

---

## R1. Banner height 26 → 32px, with matching panel offsets (for Kunjal)

**File:** `app/src/app/globals.css` (layout change, so it needs sign-off)

**Change:**
```css
.demo-banner { height: 32px; }                     /* was 26px */
.demo-banner ~ .map .map-control { top: 42px; }    /* was 36px */
.demo-banner ~ .detail { top: 32px; }              /* was 26px */
```
Optional, once the banner is taller: change `.demo-banner` padding from `0 12px` to
`0 36px` and add a left stripe to match the right one:
`background: var(--sim-stripe) left / 24px 100% no-repeat, var(--sim-stripe) right / 24px 100% no-repeat, var(--sim);`

**Why:** MASTER §5.2. The simulated-data banner has to be unmissable from the back
of a room on a projector. It's now near-white with a stripe, but at 26px it's still a
thin strip. The two offset rules keep the Layers box and the detail panel from
sliding under it.

---

## R2. Status colors: update together with the CSS tokens

**Files:** `app/src/lib/types.ts` **and** `app/src/app/globals.css` (`:root`), in the same commit

**Change:**
```ts
export const STATUS_META = {
  candidate:             { label: "Candidate",         color: "#f59e0b" }, // unchanged
  queued:                { label: "Queued",            color: "#5aaee3" }, // was #4a9fd4
  confirmed_leaking:     { label: "Confirmed leaking", color: "#f0565b" }, // was #e5484d
  confirmed_not_leaking: { label: "Not leaking",       color: "#4cbc7a" }, // was #3fa76a
  no_well:               { label: "No well",           color: "#959ca4" }, // was #8b929a
  mislocated:            { label: "Mislocated",        color: "#a893e0" }, // was #9a85d4
};
```
and in `globals.css`, set `--status-queued`, `--status-leaking`, `--status-clear`
(and `--ok`), `--status-nowell` and `--status-mislocated` to the same values.

**Why:** MASTER §1.4 and §2.2. Leaking text on `--panel-2` is only 4.56:1 today
(barely AA). The lighter values reach 5.3–8.2:1 everywhere, and work better on a
projector. The CSS tokens were deliberately left at the current values so the leak
row and gauge stay the same red as the badges and map dots. Changing only one side
would make two reds appear on screen.

---

## R3. Simulated-data banner wording

**File:** `app/src/app/page.tsx:48-49`

**Change:**
```tsx
<strong>Simulated sensor data</strong> / not field readings
```
(was `<strong>Simulated data</strong> / not field verified`)

**Why:** MASTER §5.2. Says *what* is simulated (sensor readings, not the well
candidates themselves), so judges don't conclude the whole map is fake.

---

## R4. Dashed sim outline on the detail-panel sparkline

**File:** `app/src/components/DetailPanel.tsx` (the `<svg className="spark">`, ~line 57)

**Change:** when any reading is a replay, add `sim-data`:
```tsx
className={anyReplay ? "spark sim-data" : "spark"}
```
(`anyReplay` is computed at line 109. Pass it into the sparkline component as a prop.)

**Why:** MASTER §5.3. A screenshot or glance at the chart alone must still show
that the data is fake. `.sim-data` draws a 2px dashed near-white outline inside the
box. It's an outline, not a border, so the box size doesn't change. Dashed is reserved for
simulated data.

---

## R5. Field View: sim outline, reading tag, row tag

**File:** `app/src/app/field/page.tsx`

**Changes:**
1. `.reading-card` and `.gauge`: add `sim-data` when `anyReplay` (line 258).
2. Right after the `.reading-value` number, add
   `{anyReplay && <span className="sim">Sim</span>}` so the 56px reading is never
   seen without a label.
3. Line 198: replace the plain-text `{isFake(c) ? " · sim" : ""}` with
   `{isFake(c) && <em className="tag sim">Sim</em>}`.

**Why:** MASTER §5.3. Field crews and judges see the large reading first.
Today the only cue is a small pill in the card header, and in the list it's muted
gray text that is easy to miss.

---

## R6. Candidate badge shows its score

**File:** `app/src/components/DetailPanel.tsx:130-131` (and anywhere else a
candidate status badge is rendered)

**Change:** for `status === "candidate"`, render the label as
`` `Candidate · ${c.score.toFixed(2)}` ``.

**Why:** MASTER §1.5. Candidate badges and primary action buttons are both amber.
Showing the score keeps the badge reading as data, while the buttons keep their
uppercase verb labels.

---

## R7. `ux.css`: raise 10px text to the 11px minimum (for Kunjal)

**File:** `app/src/app/ux.css` (added on `main`, imported after `globals.css` in `layout.tsx`)

**Change:** font size only, no layout change:
| Line | Rule | Was | Change to |
|---|---|---|---|
| 16 | `.live-toast-go` | `font-size: 10px` | `font-size: var(--fs-xs)` (12px, a button label) |
| 29 | `.fold > summary` | `font-size: 10px` | `font-size: var(--fs-xs)` (12px, matches `.detail-body h3`) |
| 43 | `.field-section` | `font: 700 10px var(--mono)` | `font: 700 var(--fs-xs) var(--mono)` |

**Why:** MASTER §3. Nothing goes below 11px. The P0 pass raised every 9px and 10px
size in `globals.css`, and these three new rules bring 10px text back, two of them
in the projector-facing detail panel and toast.

---

## R8. `ux.css`: use the shared color variables instead of redefining them (for Kunjal)

**File:** `app/src/app/ux.css:8-10` (`:root` block), plus `globals.css:262`

**Change:**
1. Delete `--leak: #e5484d;` and change its one use (`.live-toast.leak`, line 15)
   to `var(--status-leaking)`.
2. Delete `--ok: #3fa76a;`. `globals.css` already defines `--ok` with the same value.
3. Keep `--here: #3b82f6` (the "you are here" blue is a new color and belongs in
   one place). Move it into `globals.css` `:root` next to `--ok`, and change
   `.map-me { border: 2px solid #3b82f6 }` (globals.css:262) to `var(--here)`.
   The `#3b82f6` values in `MapView.tsx:228,234` can't read CSS variables
   (MapLibre paint). Keep them, with a comment pointing at `--here`.

**Why:** MASTER §1.4 and §1.6. Status colors live in one place. Because
`ux.css` loads after `globals.css`, its `--ok` silently wins: when R2 lightens
the status colors, the green would stay old in every rule (`globals.css` included)
and `--leak` would stay the old red, so two reds would show on screen. Today the
values happen to match, so nothing looks wrong yet.

Also worth knowing: `--here` (`#3b82f6`) and `--status-queued` (`#4a9fd4`) are
both blue. They're far enough apart in context (one is a GPS marker, the other a
status dot with a label) that this is a note, not a request.
