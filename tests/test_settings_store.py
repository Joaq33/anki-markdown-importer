"""A set of settings saved to disk and read back."""

import pytest

from anki_importer.import_run import RunSettings
from anki_importer.settings_store import load_settings, save_settings


def example() -> RunSettings:
    return RunSettings(
        vault_path="/home/user/vaults/notes",
        deck_name="Maths",
        root_notes=("Indice", "Home"),
        card_prefix="calc::",
        upsert=True,
        generate_links=False,
        throttle_seconds=0.1,
    )


def test_a_config_survives_being_written_and_read_back(tmp_path):
    path = tmp_path / "anki-importer.toml"

    save_settings(example(), path)

    assert load_settings(path) == example()


def test_every_setting_keeps_its_shape_when_read_back(tmp_path):
    path = tmp_path / "anki-importer.toml"

    save_settings(example(), path)
    reloaded = load_settings(path)

    assert reloaded.root_notes == ("Indice", "Home")
    assert reloaded.upsert is True
    assert reloaded.generate_links is False
    assert reloaded.deck_name == "Maths"
    assert reloaded.card_prefix == "calc::"


def test_reading_a_config_of_default_values_changes_nothing(tmp_path):
    path = tmp_path / "anki-importer.toml"
    save_settings(RunSettings(vault_path="/tmp/v"), path)

    assert load_settings(path) == RunSettings(vault_path="/tmp/v")


def test_reading_a_config_that_does_not_exist_gives_the_defaults(tmp_path):
    assert load_settings(tmp_path / "missing.toml") == RunSettings(vault_path="")


def test_notes_with_commas_or_quotes_survive_the_round_trip(tmp_path):
    path = tmp_path / "anki-importer.toml"
    settings = RunSettings(
        vault_path="/tmp/v", root_notes=('Nota "rara", sí', "root")
    )

    save_settings(settings, path)

    assert load_settings(path) == settings


def test_the_file_is_something_a_person_can_read_and_edit(tmp_path):
    path = tmp_path / "anki-importer.toml"
    save_settings(example(), path)

    text = path.read_text(encoding="utf-8")
    assert 'deck_name = "Maths"' in text
    assert "upsert = true" in text
