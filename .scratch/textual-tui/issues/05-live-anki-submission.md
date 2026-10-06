# 05: Live submission to AnkiConnect

**What to build:** Actually importing, from the app. Before anything is sent the
app checks it can reach AnkiConnect and, if it cannot, tells you what to do
about it instead of failing obscurely. Once connected, the discovered cards are
submitted to the chosen deck with live per-note feedback and a running tally of
added, updated, failed and skipped notes. Upsert behaves as configured, and the
run stays cancellable.

**Blocked by:** 03 — Progress, live log panel, and cancellation;
04 — Config screen and persistence.

**Status:** done

- [x] Before submitting, the app confirms it can reach AnkiConnect and reports a
      clear, actionable message when it cannot.
- [x] Submitting sends the discovered cards to the chosen deck and shows a live
      tally of added, updated, failed and skipped notes.
- [x] With upsert on, an existing note is updated rather than duplicated; with
      it off, a duplicate is skipped.
- [x] A note that fails to submit is reported and does not abort the rest of the
      run.
- [x] Cancelling part-way stops submitting and keeps the counts accurate.
- [x] All submission behaviour is tested against a substituted gateway, with no
      real Anki needed, written as failing tests first.
## Notes

- The submit and link-resolution passes themselves live in the core from ticket
  01; this ticket is the UI around them.
- The live integration test (against a real Anki on this machine) caught that
  `is_available` treated AnkiConnect's `"error": null` as a failure. Fixed to
  check truthiness.
