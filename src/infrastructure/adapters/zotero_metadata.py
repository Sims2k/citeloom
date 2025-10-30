from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Any


class ZoteroCslJsonResolver:
    def resolve(self, citekey: str | None, references_path: str) -> Mapping[str, Any] | None:
        path = Path(references_path)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return None
        if citekey:
            for it in items:
                key = it.get("id") or it.get("citekey") or it.get("citationKey")
                if key == citekey:
                    return it
        # Fallback: return the first item if citekey not provided
        return items[0] if items else None
