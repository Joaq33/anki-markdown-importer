"""Characterisation tests for card building.

Every expectation here is a literal observed from the importer before the
prefactor, so these tests pin behaviour rather than restate the implementation.
"""

import pytest

from anki_importer.card import Card
from anki_importer.card_builder import CardBuilder


@pytest.fixture
def builder() -> CardBuilder:
    return CardBuilder()


def build(builder: CardBuilder, name: str, content: str, **options) -> Card:
    return builder.build(name, content, **options)


class TestCardIdentity:
    def test_front_is_the_note_name_without_its_extension(self, builder):
        card = build(builder, "sample_math_note.md", "# Pythagoras\n")

        assert card.front == "sample_math_note"

    def test_a_configured_prefix_is_applied_to_the_front(self, builder):
        card = build(builder, "sample_math_note.md", "# Pythagoras\n", card_prefix="calc::")

        assert card.front == "calc::sample_math_note"


class TestCardTags:
    def test_tags_come_from_the_frontmatter_and_from_hashtags_in_the_body(self, builder):
        content = '---\ntags: [test, math]\n---\n# Pythagoras\n#testing\n'

        card = build(builder, "sample_math_note.md", content)

        assert card.tags == {"test", "math", "testing"}


class TestCardMath:
    def test_inline_math_survives_as_mathjax_rather_than_emphasis(self, builder):
        card = build(builder, "n.md", "Inline $x * y * z$ here\n")

        assert r"\(x * y * z\)" in card.back
        assert "<em>" not in card.back

    def test_block_math_survives_as_mathjax(self, builder):
        card = build(builder, "n.md", "$$\n\\frac{1}{2}\n$$\n")

        assert card.back == "<p>\\[\n\\frac{1}{2}\n\\]</p>\n"


class TestCardSkipping:
    def test_a_note_tagged_not_included_is_marked_to_be_skipped(self, builder):
        content = "---\ntags: [not_included]\n---\nThis should be skipped.\n"

        card = build(builder, "skipme.md", content)

        assert card.should_skip is True
        assert card.back == "This note is skipped due to the 'not_included' tag."


class TestCardLinks:
    def test_a_wiki_link_becomes_an_anki_link_placeholder_when_links_are_on(self, builder):
        card = build(builder, "n.md", "See [[linked_note|Aliased]].\n")

        assert card.staged_content == "See [Aliased|nidPENDING:linked_note]."

    def test_a_wiki_link_becomes_plain_alias_text_when_links_are_off(self, builder):
        card = build(
            builder, "n.md", "See [[linked_note|Aliased]].\n", generate_links=False
        )

        assert card.staged_content == "See Aliased."

    def test_a_wiki_link_without_an_alias_uses_the_target_as_its_text(self, builder):
        card = build(builder, "n.md", "See [[linked_note]].\n")

        assert card.staged_content == "See [linked_note|nidPENDING:linked_note]."

    def test_body_after_the_separator_is_dropped_from_the_card(self, builder):
        card = build(builder, "n.md", "Body line\n\n---\n\nTail should be dropped\n")

        assert card.staged_content == "Body line\n"


class TestCardImages:
    def test_an_embedded_image_becomes_a_placeholder(self, builder):
        card = build(builder, "n.md", "Before ![[diagram.png|300]] after\n")

        assert card.staged_content == "Before *__[image_placeholder]__* after"


class TestCardDataview:
    def test_a_dataview_formula_query_is_replaced_by_the_frontmatter_formula(self, builder):
        content = '---\nformula: "a^2 + b^2 = c^2"\n---\n`="$"+this.formula+"$"`\n'

        card = build(builder, "n.md", content)

        assert card.staged_content == "$a^2 + b^2 = c^2$"


class TestCardCallouts:
    def test_a_callout_becomes_a_styled_block_with_its_title(self, builder):
        card = build(builder, "n.md", "> [!info] My Custom Info\n> Hello world\n")

        assert '<div class="callout callout-info"' in card.back
        assert "My Custom Info" in card.back

    def test_a_callout_with_no_title_falls_back_to_its_type(self, builder):
        card = build(builder, "n.md", "> [!tip]\n> A tip\n")

        assert '<div class="callout callout-tip"' in card.back
        assert "Tip" in card.back

    def test_an_example_callout_is_muted_and_shows_its_type(self, builder):
        card = build(builder, "n.md", "> [!example] Some Example\n> Inside example\n")

        assert "opacity: 0.75" in card.back
        assert "[example]" in card.back


class TestCardRendering:
    def test_markdown_becomes_the_html_anki_renders(self, builder):
        card = build(builder, "n.md", "# Title\n\n- one\n\n**bold** and `code`\n")

        assert card.back == (
            "<h1>Title</h1>\n<ul>\n<li>one</li>\n</ul>\n"
            "<p><strong>bold</strong> and <code>code</code></p>\n"
        )