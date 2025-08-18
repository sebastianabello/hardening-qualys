from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime
from typing import Iterable, Dict, Any
import orjson

NDJSON = Iterable[Dict[str, Any]]

def write_ndjson(path: Path, items: NDJSON) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("wb") as f:
        for obj in items:
            f.write(orjson.dumps(obj))
            f.write(b"\n")
            n += 1
    return n

def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"
