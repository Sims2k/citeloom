from src.infrastructure.adapters.docling_converter import DoclingConverterAdapter
from src.infrastructure.adapters.docling_chunker import DoclingHybridChunkerAdapter


def test_docling_smoke_stub():
    conv = DoclingConverterAdapter()
    chunker = DoclingHybridChunkerAdapter()
    c = conv.convert("/tmp/source.pdf")
    chunks = chunker.chunk(c)
    assert chunks and "text" in chunks[0]
