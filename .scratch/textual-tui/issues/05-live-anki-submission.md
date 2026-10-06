# 05: Live submission to AnkiConnect

**What to build:** Actually importing, from the app. Before anything is sent the
app checks it can reach AnkiConnect and, if it cannot, tells you what to do
about it instead of failing obscurely. Once connected, the discovered cards are
submitted to the chosen deck with live per-note feedback and a running tally of
added, updated, failed and skipped notes. Upsert behaves as configured, and the
run stays cancellable.

**Blocked by:** 03 — Progress, live log panel, and cancellation;
04 — Config screen and persistence.

**Status:** ready-for-agent

- [ ] Before submitting, the app confirms it can reach AnkiConnect and reports a
      clear, actionable message when it cannot.
- [ ] Submitting sends the discovered cards to the chosen deck and shows a live
      tally of added, updated, failed and skipped notes.
- [ ] With upsert on, an existing note is updated rather than duplicated; with
      it off, a duplicate is skipped.
- [ ] A note that fails to submit is reported and does not abort the rest of the
      run.
- [ ] Cancelling part-way stops submitting and keeps the counts accurate.
- [ ] All submission behaviour is tested against a substituted gateway, with no
      real Anki needed, written as failing tests first.