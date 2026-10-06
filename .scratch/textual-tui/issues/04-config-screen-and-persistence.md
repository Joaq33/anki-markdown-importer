# 04: Config screen and persistence

**What to build:** The knobs that are currently hardcoded in the entrypoint —
vault folder, deck name, root notes, card prefix, upsert, and whether to
generate cross-note links — become a screen you can fill in and change. Your
answers are saved, so the next launch comes up with the same settings and you
can start a run immediately.

**Blocked by:** 02 — Tracer bullet: dry-run TUI.

**Status:** ready-for-agent

- [ ] A screen exposes every run setting: vault folder, deck name, root notes,
      card prefix, upsert, and link generation.
- [ ] Settings are saved when you confirm and reloaded on the next launch.
- [ ] Changing upsert or link generation changes the behaviour of the next run.
- [ ] A root note list can be edited, added to and removed from.
- [ ] Saving, reloading and each setting taking effect are covered by failing
      tests first.