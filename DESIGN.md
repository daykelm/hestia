---
name: Hestia
description: A one-operator deal desk drawn as a star atlas — every auction deal is a star placed by bid against tax roll value and sized by score.
colors:
  sky: "#0a1021"
  indigo: "#111a30"
  plate: "#16233d"
  chart: "#24374f"
  fog: "#3a4a63"
  dust: "#f2e2c9"
  quiet: "#a9b4c7"
  amber: "#ffb36b"
  red: "#ff4d2e"
  red-hover: "#ff6a4f"
typography:
  display:
    fontFamily: "EB Garamond, Iowan Old Style, Georgia, serif"
    fontSize: "1.85rem"
    fontWeight: 400
    lineHeight: 1
  headline:
    fontFamily: "EB Garamond, Iowan Old Style, Georgia, serif"
    fontSize: "2rem"
    fontWeight: 400
    lineHeight: 1.05
  section:
    fontFamily: "EB Garamond, Iowan Old Style, Georgia, serif"
    fontSize: "1.5rem"
    fontWeight: 400
    lineHeight: 1.15
  title:
    fontFamily: "EB Garamond, Iowan Old Style, Georgia, serif"
    fontSize: "1.125rem"
    fontWeight: 400
  body:
    fontFamily: "Avenir Next, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  label:
    fontFamily: "Avenir Next, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    fontFeature: "tnum"
  caption:
    fontFamily: "Avenir Next, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
rounded:
  panel: "3px"
  control: "6px"
  sheet: "14px"
  round: "50%"
spacing:
  xs: "0.5rem"
  sm: "0.75rem"
  md: "1rem"
  lg: "1.25rem"
  xl: "1.5rem"
  gutter: "clamp(1rem, 3vw, 2rem)"
components:
  button-primary:
    backgroundColor: "{colors.red}"
    textColor: "{colors.sky}"
    rounded: "{rounded.control}"
    padding: "0.55rem 0.95rem"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.red-hover}"
    textColor: "{colors.sky}"
  button-secondary:
    backgroundColor: "{colors.indigo}"
    textColor: "{colors.dust}"
    rounded: "{rounded.control}"
    padding: "0.55rem 0.95rem"
    height: "44px"
  button-toggle:
    backgroundColor: "transparent"
    textColor: "{colors.quiet}"
    rounded: "{rounded.control}"
    padding: "0.55rem 0.95rem"
    height: "44px"
  input:
    backgroundColor: "{colors.sky}"
    textColor: "{colors.dust}"
    rounded: "{rounded.control}"
    padding: "0.5rem 0.6rem"
    height: "44px"
  sky-box:
    backgroundColor: "{colors.indigo}"
    rounded: "{rounded.panel}"
    height: "clamp(300px, 50vh, 540px)"
  deal-plate:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.dust}"
    rounded: "{rounded.panel}"
    padding: "{spacing.lg}"
  index-row-selected:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.red}"
  bottom-sheet:
    backgroundColor: "{colors.plate}"
    rounded: "{rounded.sheet}"
---

# Design System: Hestia

## Overview

**Creative North Star: "The Night Desk Atlas"**

Hestia is an operator's instrument read at night: a navy sky with indigo plates, chalk-colored stardust text, and one star chart that carries the whole argument. Each deal is a star. Position is opening bid (x, log) against tax roll value (y, log); size is score. Two dashed amber lines mark "worth what it costs" (1×) and "worth twice the bid" (2×), so the deals worth a look are the bright stars far above them. Everything else on the screen is a standard, dense operating surface — a ranked index and a deal plate — that borrows the atlas's palette, italic naming, and hairline rules without borrowing its theatrics.

The register is Operate. The world lends palette, type, density, and one signature move (the sky chart with its red reticle); buttons, inputs, tables, and the phone sheet remain ordinary, legible controls. Density is high and calm: hairline 1px rules instead of cards, tabular figures for every number, and no decoration that does not carry data.

**Key Characteristics:**
- Dark, flat navy ground; depth by tonal step (sky → indigo → plate), not shadow.
- One night-vision red for the selected deal and every primary action; amber for annotations only.
- EB Garamond italic names things (properties, factors, headings, chart labels); a system sans with tabular figures carries every number.
- Score is a magnitude: dot diameter grows with score on a fixed ramp, in the chart, the index, and the plate.
- Hairline chart-blue rules divide everything; panels have barely-there 3px corners.

## Colors

A night-sky palette: three navy steps for ground and panels, chalk and slate for text, and two warm lights used sparingly.

### Primary
- **Night-Vision Red** (red): The selection and action color. Rings the selected star (reticle), colors the selected index row's address, fills the primary button (Watch this deal, Collect sales), the focus outline, text selection, and the wordmark's four-point star. Hover lifts to **Warm Signal Red** (red-hover). Error text uses it too.

### Secondary
- **Glow Amber** (amber): Annotations. The 1×/2× value lines and their italic labels, the pipeline ring around watched stars, the deal plate's place line, the status note in the top bar, the score-ceiling note, the index's bid-basis caption, the text caret, and input focus borders. Never a fill, never a button.

### Neutral
- **Night Sky** (sky): Page ground and input wells.
- **Deep Indigo** (indigo): Chart plate, filter/add forms, secondary buttons, index row hover.
- **Plate Navy** (plate): The deal plate, the selected index row, and the phone bottom sheet; one step lighter than indigo so the selected deal reads as raised.
- **Chart Blue** (chart): Every hairline — borders, table rules, coordinate block rules, chart grid (at 55% opacity), scrollbar thumb.
- **Fog** (fog): Link underlines only.
- **Stardust** (dust): Primary text, star fills, lit score pips, magnitude dots, the star glow (radial gradient from 40% to 0% opacity).
- **Slate Quiet** (quiet): Secondary text — labels, column heads, axis ticks, legend, notes, empty states, unscored star outlines, unlit pips, toggle summaries.

### Named Rules
**The One Red Rule.** Red means "this one" or "do this": the selected deal and the primary action. A screen holds one reticle and at most one red button per decision group. Do not use red for status, warnings, or decoration.

**The Amber Annotates Rule.** Amber is the chart's pencil: lines, labels, notes, rings, focus borders. It never fills a control.

## Typography

**Display Font:** EB Garamond Italic, self-hosted woff2, weights 400–500 (with Iowan Old Style, Georgia, serif)
**Body Font:** Avenir Next (with -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif)

**Character:** A light old-style italic names things the way an atlas names stars; a clean system sans with tabular figures carries money, dates, parcels, and counts. The serif is only ever italic and only ever regular weight.

### Hierarchy
- **Display** (400 italic, 1.85rem, 1): The Hestia wordmark in the top bar.
- **Headline** (400 italic, 2rem, 1.05): The selected deal's address at the top of the deal plate.
- **Section** (400 italic, 1.5rem, 1.15, balanced wrap): Lane headings ("New from auctions", "My pipeline"); a trailing count sits beside it in 0.8125rem quiet sans tabular.
- **Title** (400 italic, 1.125rem): Property addresses in the index; factor names (1.05rem) in the plate; pipeline entries (1.05rem); chart star names and value-line labels (15px).
- **Body** (400, 0.9375rem, 1.45): Everything else, including coordinate values and table cells.
- **Label** (400, 0.8125rem): Form labels, place lines, factor notes (max 60ch), off-chart note.
- **Caption** (400, 0.75rem): Table column heads, coordinate terms, bid-basis captions; chart ticks and legend at 11px.

### Named Rules
**The Italic Names Rule.** Serif italic is for names — of places, deals, factors, lanes, and chart lines. Numbers are never set in the serif.

**The Tabular Figures Rule.** Every number (money, dates, ratios, counts, parcels, scores) uses tabular figures and right-aligns in tables.

## Layout

Two columns on desk: a fluid field (chart plate above, ranked index below) and a sticky side column (minmax(320px, 27rem)) holding the selected deal plate and the pipeline lane, with a 1.5rem gap, capped at 1480px and centered. The side column sticks at 1rem from the top and scrolls internally. Page gutters are clamp(1rem, 3vw, 2rem) throughout (bar, tools, desk). The chart plate is clamp(300px, 50vh, 540px) tall. Lanes sit 1.75rem apart. The top bar is a three-part grid: wordmark, counts, actions.

At 1100px the index drops the roll ÷ bid column. At 860px everything stacks into one column: the bar wraps (counts on their own row, action buttons stretch to equal width, the button label shortens), the chart plate is fixed at 300px, the index keeps only score, property, and bid, and the deal plate becomes a bottom sheet. Below 560px chart width, the chart crops to the brightest stars (score ≥ 4 and above the 1× line, when at least five qualify), shows one grid step per decade, labels at most two stars, tags the value lines "1×"/"2×", and shows a three-step legend.

Controls are never shorter than 44px.

## Elevation & Depth

Flat. Depth is tonal: sky ground, indigo plates, a lighter plate navy for the selected deal, divided by 1px chart-blue hairlines. The only glow is in the sky chart, where each scored star carries a soft stardust radial halo (2.6× its radius). The one true shadow belongs to the phone bottom sheet, which floats over a dark scrim.

### Shadow Vocabulary
- **Sheet lift** (`box-shadow: 0 -12px 32px rgb(0 0 0 / 0.45)`): Phone bottom sheet only, paired with the scrim (`rgb(5 8 18 / 0.6)`).

### Named Rules
**The Tonal Step Rule.** To raise something, move it one navy step lighter; do not add a shadow. Shadows are reserved for surfaces that physically overlay the page (the sheet).

## Shapes

Rectilinear and quiet. Panels (chart plate, deal plate, filter and add forms) have 3px corners; controls (buttons, inputs, selects, summaries) have 6px; the phone sheet has 14px top corners. Circles are reserved for data: stars, magnitude dots, score pips (9px), the reticle. Borders are always 1px. The wordmark's mark is a four-point star drawn in SVG.

## Components

### Buttons
Standard, solid, and unglamorous; the world only lends their colors.
- **Shape:** Gently squared (6px), 44px minimum height, 0.55rem × 0.95rem padding, 1px chart-blue border.
- **Primary:** Night-vision red fill and border, night-sky text, weight 600. Used for Collect sales and Watch this deal.
- **Secondary:** Deep indigo fill, stardust text, chart-blue border (Score unchecked, Pass, Close).
- **Toggle (filter/add summaries):** Transparent, quiet text at 0.875rem; when open, stardust text and a quiet border.
- **Hover / Focus:** On fine pointers, border lightens to quiet; primary lifts to warm signal red. Press scales to 0.97 over 160ms ease-out. Focus is a 2px red outline at 2px offset. Disabled drops to 55% opacity with a progress cursor.

### Inputs / Fields
- **Style:** Night-sky well, 1px chart-blue border, 6px corners, 44px minimum height, full width; label sits above in 0.8125rem quiet sans.
- **Focus:** Border shifts to amber (160ms ease-out); no outline ring.
- **Layout:** Filter and add forms are auto-fill grids (min 11rem columns) inside an indigo 3px panel.

### Navigation
The top bar is the only navigation: wordmark, a counts line in quiet tabular sans with an in-page link to the pipeline, then actions. A status note in amber appears under it while long jobs run. A 1px chart-blue rule closes the bar.

### Ranked Index
A collapsed table with 0.75rem quiet column heads over a chart-blue rule and indigo row rules. Each row: magnitude dot and score, italic address with a quiet place line, then tabular figures. Rows are ranked by score, then roll ÷ bid. The whole row is clickable; the address link is the keyboard route. Hover tints the row indigo; the selected row takes plate navy and a red address.

### Deal Plate
The selected deal, in plate navy with a 1.25rem inset. Italic headline address, amber place line, then a two-column coordinate block (quiet caption terms over tabular values) between two hairlines, then the Watch/Pass decision row, then the score heading with its magnitude dot and the factor list: italic factor name, 9px pips (lit stardust, unlit quiet outline), and a 60ch quiet note. An amber ceiling note states what is not yet checked. Plates fade in from 40% opacity over 200ms.

### Sky Chart (signature)
An SVG plate in deep indigo. Log bid on x, log tax roll on y, chart-blue grid at 55% opacity, quiet 11px tick labels in tabular sans. Amber dashed (2 5) value lines at 1× and 2× with rotated italic labels. Stars are stardust discs with a 1px indigo stroke and a radial glow; radius is 1.5 + score × 0.8 × scale (scale from 0.55 to 1 with chart width); unscored deals are quiet outlines; passed deals sit at 35% opacity; pipeline deals carry an amber ring. Up to five of the highest-ranked stars get italic names, placed left or right to avoid other names and stars. The selected star is locked by a red reticle (circle plus four ticks) that scales in from 1.6× over 220ms. Stars are pointer targets only and stay out of the tab order. A score legend sits bottom-right.

### Bottom Sheet (phone)
Under 860px the deal plates become a fixed sheet: plate navy, 14px top corners, chart-blue top rule, sheet-lift shadow, max 72dvh with contained overscroll and safe-area padding. It slides up over 260ms on a drawer curve (cubic-bezier(0.32, 0.72, 0, 1)) over a dark scrim. Opening focuses the address; Close, the scrim, or Escape dismisses it and returns focus to the row that opened it.

## Do's and Don'ts

### Do:
- **Do** size every score as a magnitude dot on the fixed ramp — chart radius 1.5 + score × 0.8 × scale, index and plate dot 3 + score × 1.6px — so the same score looks equally bright everywhere.
- **Do** use the serif only in italic, only for names; set every figure in tabular sans.
- **Do** divide with 1px chart-blue hairlines and raise with a lighter navy step.
- **Do** keep controls standard and 44px tall; the atlas lives in the chart, not in the buttons.
- **Do** honor reduced motion: no animations, no press scale, no sheet transition.

### Don't:
- **Don't** use red for anything but the selected deal, the primary action, focus, and errors.
- **Don't** fill controls or panels with amber.
- **Don't** add shadows to panels or cards; only the phone sheet lifts.
- **Don't** put chart stars in the tab order; the index links are the keyboard route.
- **Don't** fall back to colored score pills or a grey table; score is shown as dot size.
