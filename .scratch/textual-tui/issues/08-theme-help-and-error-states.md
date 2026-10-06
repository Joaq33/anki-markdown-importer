# 08: Polish: theme, keybinding help, empty and error states

**What to build:** Making it feel like one finished tool rather than a working
demo. The screens share a consistent visual theme, a keybinding overlay explains
what you can press and where it takes you, and every "nothing here yet" or
"something went wrong" case — no root notes chosen, folder not found, Anki
unreachable, a run with no importable notes — has a designed state that says
what happened and what to do next.

**Blocked by:** 06 — Inspect and edit cards before submitting;
07 — Cross-note link resolution surfaced.

**Status:** ready-for-agent

- [ ] All screens share one theme: consistent colours, spacing and focus
      styling, and light and dark backgrounds both readable.
- [ ] A help overlay lists the keybindings for the current screen and works from
      anywhere in the app.
- [ ] Each of these has a designed state instead of a traceback or blank screen:
      no root notes chosen, folder not found, Anki unreachable, and a run that
      found no importable notes.
- [ ] Every designed state tells you what to do next.
- [ ] Screens are locked in with snapshot tests written before the styling.