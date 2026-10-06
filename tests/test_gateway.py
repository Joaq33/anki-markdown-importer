"""The AnkiConnect boundary: queries are escaped, payloads are shaped right."""

import requests

from anki_importer.gateway import AnkiConnectGateway, escape


def test_search_terms_survive_quotes_and_backslashes():
    assert escape('say "hi"') == 'say \\"hi\\"'
    assert escape("a\\b") == "a\\\\b"
    assert escape("plain") == "plain"


def test_lookups_send_the_escaped_query(monkeypatch):
    sent = []

    class FakeResponse:
        def json(self):
            return {"result": [], "error": None}

    def capture(url, json, timeout):
        sent.append(json)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", capture)

    AnkiConnectGateway().note_id_for_front('De"x', 'fr"ont')

    assert sent[0]["params"]["query"] == 'deck:"De\\"x" front:"fr\\"ont"'


def test_the_global_lookup_searches_every_deck(monkeypatch):
    sent = []

    class FakeResponse:
        def json(self):
            return {"result": [7], "error": None}

    def capture(url, json, timeout):
        sent.append(json)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", capture)

    assert AnkiConnectGateway().find_note_by_front("target") == 7
    assert sent[0]["params"]["query"] == 'Front:"target"'

def test_deck_names_lists_what_anki_knows(monkeypatch):
    class FakeResponse:
        def json(self):
            return {"result": ["Default", "Maths::Calc"], "error": None}

    monkeypatch.setattr(
        requests, "post", lambda url, json, timeout: FakeResponse()
    )

    assert AnkiConnectGateway().deck_names() == ["Default", "Maths::Calc"]


def test_deck_names_is_empty_when_anki_is_silent(monkeypatch):
    def failing(url, json, timeout):
        raise requests.exceptions.ConnectionError

    monkeypatch.setattr(requests, "post", failing)

    assert AnkiConnectGateway().deck_names() == []
