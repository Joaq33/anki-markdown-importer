import os
from unittest import TestCase
from main import AnkiHelper, Card

# Compute paths relative to this test file to avoid directory dependency
TEST_DIR = os.path.join(os.path.dirname(__file__), 'test_notes')


class TestAnkiHelper(TestCase):
    def test_check_anki_connection(self):
        # Verify that we can instantiate AnkiHelper pointing to the test notes directory
        anki_helper = AnkiHelper(folder_path=TEST_DIR, skip_submission=True)
        self.assertEqual(anki_helper.folder_path, TEST_DIR)

    def test_md_to_html_parser(self):
        content = "Inline $x * y * z$ and block $$\na_1 + b_1\n$$"
        result = AnkiHelper.md_to_html_parser(content)
        
        # Verify MathJax delimiters were injected
        self.assertIn(r'\(x * y * z\)', result)
        self.assertIn('\\[\na_1 + b_1\n\\]', result)
        # Verify markdown parser didn't corrupt the math with em tags due to the asterisks
        self.assertNotIn('<em>', result)

    def test_extract_and_replace_formula_property(self):
        anki_helper = AnkiHelper(folder_path=TEST_DIR, skip_submission=True)
        content = '> `="$"+this.formula+"$"`'
        frontmatter = {'formula': r'$(a + b)^n = \sum_{k=0}^{n} \binom{n}{k} a^{n-k} b^{k},\quad n\in \mathbb{N}$'}
        
        result = anki_helper.extract_and_replace_formula_property(content, frontmatter)
        
        expected_content = r'> $$(a + b)^n = \sum_{k=0}^{n} \binom{n}{k} a^{n-k} b^{k},\quad n\in \mathbb{N}$$'
        self.assertEqual(result, expected_content)

    def test_read_file_case_insensitive(self):
        anki_helper = AnkiHelper(folder_path=TEST_DIR, skip_submission=True)
        
        # Test case-insensitivity of file loading
        content = anki_helper.read_file_case_insensitive_simple("SAMPLE_MATH_NOTE", TEST_DIR)
        self.assertIn("Pythagoras", content)

    def test_create_card_staged_content(self):
        anki_helper = AnkiHelper(folder_path=TEST_DIR, skip_submission=True)
        
        # Read the mock file
        content = anki_helper.read_file_case_insensitive_simple("sample_math_note", TEST_DIR)
        card = anki_helper.create_card("sample_math_note.md", content)
        
        # Verify card front and frontmatter tags extraction
        self.assertEqual(card.front, "sample_math_note")
        self.assertIn("test", card.tags)
        self.assertIn("math", card.tags)
        self.assertIn("testing", card.tags)
        
        # Verify formula substitution occurred
        self.assertIn("$a^2 + b^2 = c^2$", card.staged_content)

    def test_not_included_tag_skips_card(self):
        anki_helper = AnkiHelper(folder_path=TEST_DIR, skip_submission=True)
        
        content = anki_helper.read_file_case_insensitive_simple("not_included_note", TEST_DIR)
        card = anki_helper.create_card("not_included_note.md", content)
        
        self.assertTrue(card.should_skip)
        self.assertIn("not_included", card.tags)

    def test_recursive_tracking(self):
        anki_helper = AnkiHelper(
            folder_path=TEST_DIR,
            initial_md_files=["root_note"],
            skip_submission=True
        )
        
        # Initialize tracking with root_note
        self.assertEqual(anki_helper.md_files_tracked, {"root_note"})
        
        # Run recursive traversal simulation
        anki_helper.run()
        
        # root_note points to linked_note and not_included_note
        # linked_note points to root_note (already tracked)
        # So tracked set must contain all three notes
        self.assertIn("root_note", anki_helper.md_files_tracked)
        self.assertIn("linked_note", anki_helper.md_files_tracked)
        self.assertIn("not_included_note", anki_helper.md_files_tracked)
