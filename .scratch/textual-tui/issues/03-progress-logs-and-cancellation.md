# 03: Progress, live log panel, and cancellation

**What to build:** When a run is long, the app tells you where it is and lets
you stop it. A progress indicator shows how far the run has got, a panel streams
the run's log output and errors as they happen, and a running tally shows notes
discovered, cards built and failures so far. Pressing escape cancels promptly,
keeps whatever has been discovered so far, and returns you to a usable screen.

**Blocked by:** 02 — Tracer bullet: dry-run TUI.

**Status:** ready-for-agent

- [ ] A determinate progress indicator advances during a run and reaches
      completion at the end.
- [ ] Log output and errors appear in the app's own panel as they occur, with no
      output leaking to the terminal.
- [ ] A running tally shows discovered, built and failed counts during the run.
- [ ] Cancelling mid-run stops promptly, leaves the notes discovered so far in
      the table, and leaves the app responsive and usable.
- [ ] Progress, the log panel and cancellation are each covered by failing tests
      first.