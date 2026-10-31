---
version: 1
slug: "app-py"
primary_target: "app.py"
related_targets: []
---

# Deal desk (app.py main page)

Scope: the single Hestia screen at `/`. Mode: Operate. One operator, desk and phone. Jobs: triage new auction deals by score, and work the deals already in the pipeline, clearly separated.

## Direction contract

THESIS: The deal desk is a star chart. Every collected deal is a star: its size is the score, its position is opening bid against tax roll value, so the bright stars far above the value line are the ones worth a look. Refuses the category default of a grey table with colored score pills.

OWN-WORLD: Night-sky navy ground with deep indigo panels and hairline chart-blue rules. Chalk stardust text. One night-vision red rings the deal under the eye and marks every primary action; glow amber carries annotations. A light serif italic names each property; small tabular figures carry money, dates, and parcels. Dot diameter follows a fixed 1 to 10 magnitude ramp.

STORY: He opens Hestia, sees which stars are biggest and highest above the value line, picks one, reads what each public record said and what was not checked, then watches or passes it. His pipeline sits in its own lane.

FIRST VIEWPORT: Top bar with the wordmark, counts, Score unchecked, and Collect. Left about 60 percent: the chart plate (bid across, tax roll up, log scales, value lines at 1x and 2x, stars sized by score, the selected one ringed red), the ranked index of deals under it. Right: the selected deal plate (italic address, coordinates, five factor magnitudes, Watch and Pass), then My pipeline. Phone: bar, chart cropped to the brightest stars, index, the selected deal as a bottom sheet.

FORM: catalog challenger notation-diagram-systems-star-atlas, adopted by the user over the assigned direction. seed:57df3fb6dc3a3843

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- Legal and liens factors are not checked yet; the deal plate must say so plainly.
- Repairs, Pursue / Pass / Watch as a separate decision, and the buyer list are not built.
