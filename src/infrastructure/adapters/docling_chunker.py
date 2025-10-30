from typing import Mapping, Any, Sequence


class DoclingHybridChunkerAdapter:
    def chunk(self, conversion: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for page in conversion.get("pages", []):
            text = page.get("text", "")
            heading = "/".join(page.get("headings", [])) if page.get("headings") else None
            chunks.append(
                {
                    "id": f"{conversion.get('source_path','')}:p{page.get('index',0)}:0",
                    "docId": conversion.get("source_path"),
                    "projectId": "",
                    "text": text,
                    "page_span": [page.get("index", 0), page.get("index", 0)],
                    "section": heading,
                    "chunkIndex": 0,
                    "sectionPath": page.get("headings", []) or [],
                }
            )
        return chunks
