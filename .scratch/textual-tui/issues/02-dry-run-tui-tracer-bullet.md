# 02: Tracer bullet: dry-run TUI

**What to build:** Launching the app opens a full-screen Textual interface.
You choose a vault folder and the root notes to start from, press Run, and
watch the wiki-link graph get traversed: each discovered note becomes a card and
appears in a table showing its front, tags and whether it will be skipped. This
is a dry run — nothing is sent anywhere and Anki does not need to be running.

**Blocked by:** 01 — Prefactor: pure import core + AnkiConnect gateway.

**Status:** done

- [x] The app launches full-screen and discovers notes and builds cards from the
      chosen folder and root notes, listing each one with front, tags and skip
      state.
- [x] Discovery continues past the starting notes by following the wiki-links it
      finds, each note appearing exactly once.
- [x] No card is submitted to Anki, and the app runs with AnkiConnect stopped.
- [x] Nothing is printed to the terminal outside the app's own screen.
- [x] Invalid input (missing folder, no root notes) shows a visible message
      rather than a traceback.
- [x] The screen is driven by a failing test through Textual's test harness
      before the UI is built.