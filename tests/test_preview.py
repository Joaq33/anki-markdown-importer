"""A card's back, as a reader would take it away, without the HTML."""

import pytest

from anki_importer.preview import plain_preview


def test_a_paragraph_reads_as_its_text():
    assert (
        plain_preview("<p>Body here <strong>bold</strong> and `code`.</p>\n")
        == "Body here bold and `code`."
    )


def test_an_image_placeholder_reads_as_its_name():
    back = "<p>Before <em><strong>[image_placeholder]</strong></em> after</p>\n"

    assert plain_preview(back) == "Before [image_placeholder] after"


def test_a_link_placeholder_reads_as_the_text_anki_would_show():
    back = "<p>See [Aliased|nidPENDING:linked_note].</p>\n"

    assert plain_preview(back) == "See [Aliased|nidPENDING:linked_note]."


def test_a_list_reads_one_bulleted_item_per_line():
    back = "<ul>\n<li>one</li>\n<li>two</li>\n</ul>\n"

    assert plain_preview(back) == "\u2022 one\n\u2022 two"


def test_mathjax_survives_without_the_markup_around_it():
    back = "<p>Inline \\(x * y\\) and</p>\n<p>\\[\nq\n\\]</p>\n"

    assert plain_preview(back) == "Inline \\(x * y\\) and\n\\[\nq\n\\]"


def test_entities_are_unescaped():
    assert plain_preview("<p>a &amp; b &lt;3</p>") == "a & b <3"


def test_a_callout_reads_as_its_title_then_its_body():
    back = (
        '<div class="callout callout-info" style="x">\n'
        '<div class="callout-title" style="y">My Custom Info</div>\n\n'
        '<div class="callout-content" style="z">\n\nHello world\n\n</div>\n\n</div>'
    )

    assert plain_preview(back) == "My Custom Info\nHello world"


def test_nothing_reads_as_nothing():
    assert plain_preview("") == ""