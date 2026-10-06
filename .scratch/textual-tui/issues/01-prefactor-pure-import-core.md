# 01: Prefactor: pure import core + AnkiConnect gateway

**What to build:** Nothing user-visible. Today one class discovers notes from
the wiki-link graph, builds cards, talks to AnkiConnect and keeps run counters,
with logging configured as a side effect of import. This ticket separates the
work into a pure import core (graph discovery and card building, callable with
no network and no terminal side effects) and an AnkiConnect gateway that owns
the network calls and the run counters. The same import run still produces the
same cards as before.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] The existing test suite passes unchanged after the split.
- [x] Card building and note discovery can be driven with no Anki running and
      without a terminal or log file sink configured.
- [x] Importing the project no longer installs logging sinks as a side effect;
      logging is configured only when the app starts.
- [x] Network calls are confined to one gateway seam that tests can substitute.
- [x] The behaviour the tests lock in is written first, as failing tests.

## Notes

The submit and link-resolution halves of ticket 05 landed here as part of the
core, with their tests at the gateway seam; ticket 05 is left with the UI wiring.

Deviations from the old behaviour, both deliberate:

- A note tagged `not_included` keeps its file extension on the front, as before.
  Looks like a bug; left alone so this stays a pure move.
- A single-string `tags:` in frontmatter is treated as one tag instead of being
  iterated character by character.