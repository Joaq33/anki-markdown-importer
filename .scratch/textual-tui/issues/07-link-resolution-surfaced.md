# 07: Cross-note link resolution surfaced

**What to build:** Notes link to each other, and the link can only be written
once the target note has a real id in Anki — so this runs as a second pass after
import. In the app that pass is visible: you see it start, see the tally of links
resolved as it goes, and at the end you are told how many resolved and exactly
which note targets could not be found, instead of only finding out later from
the logs.

**Blocked by:** 05 — Live submission to AnkiConnect.

**Status:** ready-for-agent

- [ ] Link resolution runs as its own visible step after submission, with
      progress as it goes.
- [ ] The final summary reports how many links were resolved and how many were
      not.
- [ ] Every unresolved link names the note whose target could not be found, so
      you can go fix the wiki-link.
- [ ] The second pass runs only when link generation is enabled, and the step is
      skipped visibly when it is not.
- [ ] Resolution counts and unresolved-target reporting are covered by failing
      tests first, with no real Anki needed.