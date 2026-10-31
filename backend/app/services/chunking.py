import re
from dataclasses import dataclass, field


@dataclass
class ChunkPayload:
    """Represents a generated layout-aware chunk ready for embedding and storage."""

    chunk_index: int
    page_number: int | None
    chunk_type: str
    content: str
    metadata_json: dict[str, object] = field(default_factory=dict)


class LayoutAwareChunker:
    """
    Intelligent layout-aware chunker that:
    1. Detects and preserves Markdown tables intact (with header repetition if split).
    2. Respects paragraph and heading boundaries.
    3. Injects document and page contextual prefixes into every chunk.
    4. Applies sliding character overlap across narrative chunks.
    """

    def __init__(
        self,
        max_chunk_chars: int = 1000,
        chunk_overlap_chars: int = 150,
    ) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.chunk_overlap_chars = chunk_overlap_chars

    def chunk_document_pages(
        self,
        pages: list[tuple[int, str]],  # (page_no, page_text)
        filename: str = "document",
    ) -> list[ChunkPayload]:
        """
        Processes a list of (page_no, page_text) tuples and returns indexed ChunkPayloads.
        """
        all_chunks: list[ChunkPayload] = []
        current_chunk_idx = 0

        for page_no, page_text in pages:
            if not page_text or not page_text.strip():
                continue

            page_blocks = self._split_into_blocks(page_text)

            for block_type, block_content in page_blocks:
                if block_type == "table":
                    table_chunks = self._chunk_table_block(
                        block_content=block_content,
                        page_no=page_no,
                        filename=filename,
                        start_idx=current_chunk_idx,
                    )
                    all_chunks.extend(table_chunks)
                    current_chunk_idx += len(table_chunks)
                else:
                    text_chunks = self._chunk_text_block(
                        block_content=block_content,
                        page_no=page_no,
                        filename=filename,
                        start_idx=current_chunk_idx,
                    )
                    all_chunks.extend(text_chunks)
                    current_chunk_idx += len(text_chunks)

        return all_chunks

    def _split_into_blocks(self, text: str) -> list[tuple[str, str]]:
        """
        Partitions page text into narrative blocks and markdown table blocks.
        Returns list of (type, content) where type is 'table' or 'text'.
        """
        lines = text.split("\n")
        blocks: list[tuple[str, str]] = []
        current_type: str | None = None
        current_lines: list[str] = []

        table_line_regex = re.compile(r"^\s*\|.*\|\s*$")

        for line in lines:
            is_table_line = bool(table_line_regex.match(line))
            line_type = "table" if is_table_line else "text"

            if current_type is None:
                current_type = line_type
                current_lines.append(line)
            elif current_type == line_type:
                current_lines.append(line)
            else:
                # Flush existing block
                content = "\n".join(current_lines).strip()
                if content:
                    blocks.append((current_type, content))
                current_type = line_type
                current_lines = [line]

        if current_lines:
            content = "\n".join(current_lines).strip()
            if content and current_type:
                blocks.append((current_type, content))

        return blocks

    def _chunk_table_block(
        self,
        block_content: str,
        page_no: int,
        filename: str,
        start_idx: int,
    ) -> list[ChunkPayload]:
        """
        Preserves Markdown tables intact. If table exceeds max_chunk_chars,
        splits row-by-row while preserving the table header in all sub-chunks.
        """
        context_prefix = f"[Document: {filename} | Page: {page_no} | Type: Table]\n"
        full_content = context_prefix + block_content

        # Fits comfortably in a single chunk
        if len(full_content) <= self.max_chunk_chars:
            return [
                ChunkPayload(
                    chunk_index=start_idx,
                    page_number=page_no,
                    chunk_type="table",
                    content=full_content,
                    metadata_json={
                        "filename": filename,
                        "page_number": page_no,
                        "is_table": True,
                        "char_count": len(full_content),
                    },
                )
            ]

        # Table is oversized: split rows while retaining headers
        lines = [line for line in block_content.split("\n") if line.strip()]
        if len(lines) < 3:
            # Not a standard table with header + separator + rows, return as is
            return [
                ChunkPayload(
                    chunk_index=start_idx,
                    page_number=page_no,
                    chunk_type="table",
                    content=full_content,
                    metadata_json={"filename": filename, "page_number": page_no, "is_table": True},
                )
            ]

        header_lines = lines[:2]  # Header and separator (| col | col |\n|---|---|)
        header_text = "\n".join(header_lines) + "\n"
        data_rows = lines[2:]

        chunks: list[ChunkPayload] = []
        current_rows: list[str] = []
        current_idx = start_idx

        for row in data_rows:
            trial_table = header_text + "\n".join(current_rows + [row])
            trial_content = context_prefix + trial_table

            if len(trial_content) > self.max_chunk_chars and current_rows:
                # Flush current table
                flushed_table = header_text + "\n".join(current_rows)
                chunks.append(
                    ChunkPayload(
                        chunk_index=current_idx,
                        page_number=page_no,
                        chunk_type="table",
                        content=context_prefix + flushed_table,
                        metadata_json={
                            "filename": filename,
                            "page_number": page_no,
                            "is_table": True,
                            "is_split_table": True,
                            "row_count": len(current_rows),
                        },
                    )
                )
                current_idx += 1
                current_rows = [row]
            else:
                current_rows.append(row)

        if current_rows:
            flushed_table = header_text + "\n".join(current_rows)
            chunks.append(
                ChunkPayload(
                    chunk_index=current_idx,
                    page_number=page_no,
                    chunk_type="table",
                    content=context_prefix + flushed_table,
                    metadata_json={
                        "filename": filename,
                        "page_number": page_no,
                        "is_table": True,
                        "is_split_table": True,
                        "row_count": len(current_rows),
                    },
                )
            )

        return chunks

    def _chunk_text_block(
        self,
        block_content: str,
        page_no: int,
        filename: str,
        start_idx: int,
    ) -> list[ChunkPayload]:
        """
        Splits narrative text into chunks using paragraph boundaries and sliding overlap.
        """
        context_prefix = f"[Document: {filename} | Page: {page_no}]\n"
        available_chars = max(200, self.max_chunk_chars - len(context_prefix))

        paragraphs = [p.strip() for p in block_content.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [block_content]

        chunks: list[ChunkPayload] = []
        current_chunk_text = ""
        current_idx = start_idx

        for para in paragraphs:
            # If paragraph itself is longer than available chars, split into sentences
            if len(para) > available_chars:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                for sentence in sentences:
                    if len(current_chunk_text) + len(sentence) + 1 <= available_chars:
                        current_chunk_text = (
                            f"{current_chunk_text} {sentence}".strip()
                            if current_chunk_text
                            else sentence
                        )
                    else:
                        if current_chunk_text:
                            chunks.append(
                                ChunkPayload(
                                    chunk_index=current_idx,
                                    page_number=page_no,
                                    chunk_type="text",
                                    content=context_prefix + current_chunk_text,
                                    metadata_json={
                                        "filename": filename,
                                        "page_number": page_no,
                                        "char_count": len(current_chunk_text),
                                    },
                                )
                            )
                            current_idx += 1
                            # Overlap from tail of previous chunk
                            overlap = current_chunk_text[-self.chunk_overlap_chars :]
                            current_chunk_text = f"{overlap} {sentence}".strip()
                        else:
                            current_chunk_text = sentence
            else:
                if len(current_chunk_text) + len(para) + 2 <= available_chars:
                    current_chunk_text = (
                        f"{current_chunk_text}\n\n{para}".strip()
                        if current_chunk_text
                        else para
                    )
                else:
                    if current_chunk_text:
                        chunks.append(
                            ChunkPayload(
                                chunk_index=current_idx,
                                page_number=page_no,
                                chunk_type="text",
                                content=context_prefix + current_chunk_text,
                                metadata_json={
                                    "filename": filename,
                                    "page_number": page_no,
                                    "char_count": len(current_chunk_text),
                                },
                            )
                        )
                        current_idx += 1
                        overlap = current_chunk_text[-self.chunk_overlap_chars :]
                        current_chunk_text = f"{overlap}\n\n{para}".strip()
                    else:
                        current_chunk_text = para

        if current_chunk_text:
            chunks.append(
                ChunkPayload(
                    chunk_index=current_idx,
                    page_number=page_no,
                    chunk_type="text",
                    content=context_prefix + current_chunk_text,
                    metadata_json={
                        "filename": filename,
                        "page_number": page_no,
                        "char_count": len(current_chunk_text),
                    },
                )
            )

        return chunks
