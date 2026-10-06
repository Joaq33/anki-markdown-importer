# 10: Modernize the main screen: layout rhythm + visual theme

**What to build:** The main screen today is one loose vertical stack in
default Textual chrome: oversized empty inputs, a three-row status stack, and
harsh default blue. Give it a designed look: a registered custom theme
(replacing default blue/green with a cohesive palette), framed panels with
titles for Source / Cards / Log, a single-row status strip (notice + compact
progress, no ETA noise), tighter control spacing, and the stage reflected in
the header.

**Blocked by:** 09 — Better selectors.

**Status:** done

- [x] A custom `anki` theme is registered and default; no screen depends on
      stock Textual blue/green for its look.
- [x] Source fields live in a tinted zone, the log in a tinted zone (borders
      would cost rows the table needs; space-then-tint per better-layout)
      panels; status is one row (notice + progress, no ETA).
- [x] At 80x24 the table still gets the majority of rows; chrome is compact.
- [x] Every existing behaviour test passes unchanged; snapshots are
      regenerated and eyeballed before accepting.
- [x] Light and dark both render from the theme (single source of palette).
## Notes

- Dropped before building: border-titled panels (4 rows the table needs more)
  and the header stage subtitle (the notice bar already owns stage; one
  source). The ticket describes the tint approach instead.
- A side-by-side notice+progress row was tried and reverted: the bar jammed
  into long notices. Stacked notice over slim progress, minus ETA and minus
  the duplicated counts line, fixed the sprawl.
- The empty counts line now costs zero rows (height 0 until it has news).
