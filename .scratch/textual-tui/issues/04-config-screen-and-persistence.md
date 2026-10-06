# 04: Config screen and persistence

**What to build:** The knobs that are currently hardcoded in the entrypoint —
vault folder, deck name, root notes, card prefix, upsert, and whether to
generate cross-note links — become a screen you can fill in and change. Your
answers are saved, so the next launch comes up with the same settings and you
can start a run immediately.

**Blocked by:** 02 — Tracer bullet: dry-run TUI.

**Status:** done

- [x] A screen exposes every run setting: vault folder, deck name, root notes,
      card prefix, upsert, and link generation.
- [x] Settings are saved when you confirm and reloaded on the next launch.
- [x] Changing upsert or link generation changes the behaviour of the next run.
- [x] A root note list can be edited, added to and removed from.
- [x] Saving, reloading and each setting taking effect are covered by failing
      tests first.
## Notes

- The config file lives next to where the app is launched
  (`./anki-importer.toml` by default). It is hand-editable TOML.
- The pause between notes is kept in the file but has no field on the screen.
  It is plumbing, not a setting a user thinks about per run.
