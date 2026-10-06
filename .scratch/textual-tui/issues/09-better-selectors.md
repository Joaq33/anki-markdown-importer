# 09: Better selectors for vaults, roots and decks

**What to build:** No more typing raw paths and comma-separated note names
from memory. The vault field gets a Browse button opening a folder picker;
the roots field gets a Roots button opening a checklist of every note in the
vault; and the fields suggest as you type (note names in roots, deck names
from Anki where it is reachable).

**Blocked by:** 08 — Theme, keybinding help overlay, empty and error states.

**Status:** done

- [x] A Browse button next to the vault field opens a folder picker rooted
      near the current value; choosing fills the field.
- [x] A Roots button next to the roots field lists every note in the vault
      with its current roots pre-ticked; applying fills the field.
- [x] Typing in roots suggests note names, completing only the name being
      typed; typing in deck suggests the decks Anki knows.
- [x] Picking from an empty or missing vault says so instead of showing an
      empty list with no explanation.
- [x] Each selector is driven by a failing test through the UI before it is
      built.
## Notes

- Completion is accepted with Right-arrow (Textual's convention), not Tab:
  Tab moves focus. Found while testing.
- Setting an input's value leaves the cursor at 0, so picker fills move it
  to the end; the completion tests do the same before pressing Right.
- Deck names load once per launch on a worker; unreachable Anki fails
  silent and fast (localhost refuses immediately).
