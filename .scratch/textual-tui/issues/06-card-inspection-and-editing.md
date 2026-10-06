# 06: Inspect and edit cards before submitting

**What to build:** Catching a mistake before it reaches Anki. Select any
discovered card and see what it actually contains — its front, its back as it
will render in Anki, and its tags. Fix the front or the tags, or mark that card
to be left out of the run. What you see is what gets submitted.

**Blocked by:** 05 — Live submission to AnkiConnect.

**Status:** ready-for-agent

- [ ] Selecting a card shows its front, its back as Anki would render it, and
      its tags.
- [ ] You can change a card's front and tags, and mark a card to be skipped,
      and those changes are what get submitted.
- [ ] Editing one card leaves the rest of the run untouched, including cards
      already submitted.
- [ ] Edits survive revisiting the card and submitting the run.
- [ ] Selection, editing and skip-marking are each covered by failing tests
      first.