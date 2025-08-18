from __future__ import annotations
from pathlib import Path
from typing import Iterable, Dict, Any
import httpx
import orjson

class BulkIngestor:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def bulk_ndjson(self, index: str, docs: Iterable[Dict[str, Any]]) -> dict:
        # Construir payload _bulk (acción index + documento por línea)
        lines: list[bytes] = []
        header = orjson.dumps({"index": {"_index": index}})
        for doc in docs:
            lines.append(header)
            lines.append(orjson.dumps(doc))
        payload = b"\n".join(lines) + b"\n"

        headers = {
            "Content-Type": "application/x-ndjson",
            "Authorization": f"ApiKey {self.api_key}",
        }
        url = f"{self.base_url}/_bulk"
        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, content=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        # Retornar métricas mínimas
        errors = data.get("errors", False)
        items = data.get("items", [])
        return {
            "errors": errors,
            "items": len(items),
        }
