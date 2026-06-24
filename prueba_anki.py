import json
import requests

from dataclasses import dataclass
from dataclasses import field
from typing import Optional

@dataclass
class Card:
    front: str = ""
    back: str = ""
    frontmatter: dict[str, list[str]] = None
    staged_content: str = ""
    should_skip: bool = False
    tags: set[str] = field(default_factory=set)

card = Card()
card.front='example_title'
card.back="example back"
card.tags=[]
deck_name='test_fabric_data_engineer'
asd = {
            "action": "addNote",
            "version": 6,
            "params": {
                "note": {
                    "deckName": deck_name,
                    "modelName": "Basic",
                    "fields": {
                        "Front": card.front,
                        "Back": card.back
                    },
                    "tags": list(card.tags) if card.tags else [],
                }
            }
        }
print(json.dumps(asd))
response = requests.post("http://localhost:8765", json=asd)
print("response",response.json())
