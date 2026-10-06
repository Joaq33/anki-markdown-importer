# 08: Polish: theme, keybinding help, empty and error states

**What to build:** Making it feel like one finished tool rather than a working
demo. The screens share a consistent visual theme, a keybinding overlay explains
what you can press and where it takes you, and every "nothing here yet" or
"something went wrong" case — no root notes chosen, folder not found, Anki
unreachable, a run with no importable notes — has a designed state that says
what happened and what to do next.

**Blocked by:** 06 — Inspect and edit cards before submitting;
07 — Cross-note link resolution surfaced.

**Status:** done

- [x] All screens share one theme: consistent colours, spacing and focus
      styling, and light and dark backgrounds both readable.
- [x] A help overlay lists the keybindings for the current screen and works from
      anywhere in the app.
- [x] Each of these has a designed state instead of a traceback or blank screen:
      no root notes chosen, folder not found, Anki unreachable, and a run that
      found no importable notes.
- [x] Every designed state tells you what to do next.
- [x] Screens are locked in with snapshot tests written before the styling.
## Notes

- Help opens with `?` (or a Help button, since fields eat keystrokes while
  you type) from the main and settings screens; every app keybinding is
  cross-checked against it by a test.
- All colour comes from theme variables, so light and dark renderings stay
  readable with no extra work.
- The table owns the keyboard on launch, so shortcuts work immediately and
  identically however the app is started. Typing takes focus when you click
  or Tab into a field.
- The idle progress bar is determinate-empty on purpose: an indeterminate
  pulse never renders the same frame twice, which made the main snapshot
  flaky. Found while stabilising the snapshots.
- Snapshots run against the repo's fixture vault through a relative path, so
  they hold on any machine whatever else ran before them.
