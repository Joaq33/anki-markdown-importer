# Spec: Textual TUI for the Anki Markdown Importer

## What we are building

Replace the hardcoded, fire-and-forget script entrypoint with a full-screen
terminal UI for importing an Obsidian vault into Anki: configure the run, watch
it happen live, inspect what will be imported, and fix problems before anything
is submitted.

## Decisions

- **Library: Textual.** Widget framework with CSS, background workers and a
  built-in test harness, which is what a TUI built test-first needs.
- **Test runner: pytest**, added as a dev dependency alongside
  pytest-textual-snapshot. Existing `unittest` tests keep passing.
- **The TUI replaces the non-interactive entrypoint.** There is no separate
  scripted run path.
- **Development is test-first.** Each ticket's behaviour is driven by a failing
  test before it is implemented.

## Constraints

- Import behaviour must not change: wiki-link graph traversal, tag extraction,
  MathJax preservation, callout formatting, upsert and cross-note link
  resolution all behave as they do today.
- The importer must not write to stdout while the app owns the terminal.
- A real Anki instance is never required to run the test suite.

## Out of scope

- Changing card content, tags or link semantics.
- Any change to how AnkiConnect payloads are built.