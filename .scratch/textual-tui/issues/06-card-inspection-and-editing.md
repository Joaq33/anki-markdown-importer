# 06: Inspect and edit cards before submitting

**What to build:** Catching a mistake before it reaches Anki. Select any
discovered card and see what it actually contains — its front, its back as it
will render in Anki, and its tags. Fix the front or the tags, or mark that card
to be left out of the run. What you see is what gets submitted.

**Blocked by:** 05 — Live submission to AnkiConnect.

**Status:** done

- [x] Selecting a card shows its front, its back as Anki would render it, and
      its tags.
- [x] You can change a card's front and tags, and mark a card to be skipped,
      and those changes are what get submitted.
- [x] Editing one card leaves the rest of the run untouched, including cards
      already submitted.
- [x] Edits survive revisiting the card and submitting the run.
- [x] Selection, editing and skip-marking are each covered by failing tests
      first.
## Notes

- The back cannot be edited, only viewed: Anki builds it, and editing
  generated HTML by hand is a way to lose the plot. Front, tags and the skip
  flag are what you can change.
- The terminal cannot render Anki's HTML, so the detail shows a plain-text
  reading of the back (one line per thought, list items bulleted).
- The table's rows are keyed by position now, so renaming a card no longer
  moves it.
