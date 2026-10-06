"""The roots field completes the name being typed, nothing else."""

import pytest

from anki_importer.tui.suggesters import NoteSuggester

NOTES = ["linked_note", "not_included_note", "root_note"]


@pytest.fixture
def suggest():
    return NoteSuggester(NOTES)


async def test_a_single_name_is_completed(suggest):
    assert await suggest.get_suggestion("roo") == "root_note"


async def test_only_the_name_being_typed_is_completed(suggest):
    assert await suggest.get_suggestion("root_note, link") == "root_note, linked_note"


async def test_the_casing_you_typed_is_left_alone(suggest):
    assert await suggest.get_suggestion("Root, LIN") == "Root, linked_note"


async def test_a_name_you_finished_gets_no_suggestion(suggest):
    assert await suggest.get_suggestion("root_note") is None
    assert await suggest.get_suggestion("root_note, linked_note") is None


async def test_a_name_that_matches_nothing_gets_no_suggestion(suggest):
    assert await suggest.get_suggestion("zzz") is None


async def test_an_empty_segment_gets_no_suggestion(suggest):
    assert await suggest.get_suggestion("") is None
    assert await suggest.get_suggestion("root_note, ") is None
    assert await suggest.get_suggestion("root_note,") is None