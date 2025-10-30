from typing import Mapping, Any


class DoclingConverterAdapter:
    def convert(self, source_path: str) -> Mapping[str, Any]:
        # Placeholder: returns a minimal structure mimicking a conversion result
        # In Phase F integration, replace with real Docling conversion
        return {
            "source_path": source_path,
            "pages": [
                {"index": 1, "text": "Sample page text", "headings": ["Introduction"]}
            ],
            "metadata": {},
        }
