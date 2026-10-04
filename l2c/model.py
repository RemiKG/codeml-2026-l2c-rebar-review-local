"""Internal observations keep context beside the sponsor's exact record shape."""
from dataclasses import dataclass, field
from typing import Any
import hashlib, json, re, unicodedata

FAMILIES = ("fondation", "poutre", "mur_refend", "colonne", "dalle")
SHEET_FAMILY = {"1": "fondation", "3": "poutre", "4": "mur_refend", "5": "colonne", "6": "dalle"}

def normalized(value):
    text = unicodedata.normalize("NFKD", str(value or "")).upper()
    return "".join(c for c in text if not unicodedata.combining(c))

def identifier(value):
    return re.sub(r"[^A-Z0-9]", "", normalized(value))

def stable_id(*values):
    data = json.dumps(values, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:24]

@dataclass
class TextLine:
    text: str
    bbox: tuple
    block: int = 0
    method: str = "native"

@dataclass
class Observation:
    record: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)
    def export(self):
        return self.record

def center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)

def union_box(boxes):
    boxes = list(boxes)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))
