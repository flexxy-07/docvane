from backend.app.services.chunking import LayoutAwareChunker


def test_chunking_narrative_text() -> None:
    chunker = LayoutAwareChunker(max_chunk_chars=300, chunk_overlap_chars=50)
    page_text = (
        "This is paragraph one introducing the document.\n\n"
        "This is paragraph two containing detailed information about the specifications.\n\n"
        "This is paragraph three summarizing everything."
    )
    chunks = chunker.chunk_document_pages([(1, page_text)], filename="contract.pdf")

    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.page_number == 1
        assert chunk.chunk_type == "text"
        assert "[Document: contract.pdf | Page: 1]" in chunk.content


def test_chunking_preserves_table() -> None:
    chunker = LayoutAwareChunker(max_chunk_chars=1000)
    table_text = (
        "Here is some preceding text.\n\n"
        "| Item | Quantity | Price |\n"
        "|---|---|---|\n"
        "| Widget A | 10 | $50.00 |\n"
        "| Widget B | 5 | $25.00 |\n\n"
        "And here is trailing text."
    )
    chunks = chunker.chunk_document_pages([(1, table_text)], filename="invoice.pdf")

    table_chunks = [c for c in chunks if c.chunk_type == "table"]
    assert len(table_chunks) == 1
    assert "| Item | Quantity | Price |" in table_chunks[0].content
    assert "| Widget A | 10 | $50.00 |" in table_chunks[0].content
    assert table_chunks[0].metadata_json.get("is_table") is True


def test_chunking_oversized_table_retains_headers() -> None:
    # Set small max_chunk_chars so the table is forced to split
    chunker = LayoutAwareChunker(max_chunk_chars=200)

    rows = "\n".join([f"| Row {i} | Some very long description text {i} |" for i in range(10)])
    oversized_table = f"| ID | Description |\n|---|---|\n{rows}"

    chunks = chunker.chunk_document_pages([(1, oversized_table)], filename="table_doc.pdf")

    table_chunks = [c for c in chunks if c.chunk_type == "table"]
    assert len(table_chunks) > 1

    # Every split table chunk must retain the header
    for tc in table_chunks:
        assert "| ID | Description |" in tc.content
        assert "|---|---|" in tc.content
        assert tc.metadata_json.get("is_split_table") is True


def test_chunking_empty_page() -> None:
    chunker = LayoutAwareChunker()
    chunks = chunker.chunk_document_pages([(1, ""), (2, "   \n\n  ")], filename="empty.pdf")
    assert len(chunks) == 0
