"""
Milestone 3 — Chunking
Reads cleaned documents from documents/*.json and applies a hybrid
paragraph-aware chunking strategy with overlap, matching the spec in planning.md.

Chunk size: 250–300 tokens  (~1100 chars at 4 chars/token)
Overlap:     40–50 tokens  (~180 chars)

Strategy: split cleaned_text on blank lines into atomic paragraph units,
then greedily merge consecutive paragraphs until the target size is reached.
The next chunk starts by backing up from the boundary so the trailing
paragraphs of the previous chunk become the leading paragraphs of the next,
achieving paragraph-aligned overlap without splitting headings.
"""

import json
import re
from pathlib import Path

DOCUMENTS_DIR = Path(__file__).parent / "documents"
CHUNKS_PATH = Path(__file__).parent / "chunks.json"

# 1 token ≈ 4 chars for English prose — converts planning.md token budgets
# to character counts without requiring a tokenizer at ingest time.
_CHARS_PER_TOKEN = 4

TARGET_TOKENS = 275   # midpoint of the 250–300 range in planning.md
OVERLAP_TOKENS = 45   # midpoint of the 40–50 range in planning.md

TARGET_CHARS = TARGET_TOKENS * _CHARS_PER_TOKEN   # 1100
OVERLAP_CHARS = OVERLAP_TOKENS * _CHARS_PER_TOKEN  # 180

# Tail chunks below this size are absorbed into the preceding chunk rather than
# emitted as standalone fragments.  50 tokens (~200 chars) is the minimum
# useful retrieval unit for this domain.
MIN_TOKENS = 50
MIN_CHARS = MIN_TOKENS * _CHARS_PER_TOKEN  # 200


def _split_paragraphs(text: str) -> list[str]:
    """Split on one or more blank lines; drop empty segments."""
    return [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]


def chunk_text(
    text: str,
    property_name: str,
    source_url: str,
    doc_id: str,
    target_chars: int = TARGET_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[dict]:
    """
    Hybrid paragraph + fixed-size chunking with overlap.

    Steps:
    1. Split text into paragraphs (atomic units — preserves amenity lists).
    2. Greedily merge paragraphs until target_chars is reached.
    3. Emit the merged block as a chunk, tagged with property metadata.
    4. Back up from the chunk boundary by overlap_chars worth of paragraphs
       so the next chunk begins with shared context.  Always advances at least
       one paragraph to prevent infinite loops on oversized single paragraphs.
    """
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks = []
    start = 0

    while start < len(paragraphs):
        # --- build chunk: greedily add paragraphs up to target_chars ---
        end = start
        current_len = 0

        while end < len(paragraphs):
            sep = 2 if end > start else 0  # "\n\n" separator between paragraphs
            para_len = len(paragraphs[end])
            if end > start and current_len + sep + para_len > target_chars:
                break
            current_len += sep + para_len
            end += 1

        chunk_body = "\n\n".join(paragraphs[start:end])
        chunks.append({
            "chunk_id": f"{doc_id}_chunk_{len(chunks)}",
            "doc_id": doc_id,
            "property_name": property_name,
            "source_url": source_url,
            "text": chunk_body,
            "char_count": len(chunk_body),
            "approx_tokens": len(chunk_body) // _CHARS_PER_TOKEN,
        })

        # If this chunk reached the end of the document, stop.  Without this
        # check the overlap calculation would create a new start inside the
        # current chunk and emit a tiny shadow chunk with no new content.
        if end >= len(paragraphs):
            break

        # --- find next start: back up from `end` to achieve overlap ---
        # Accumulate paragraph lengths from the tail of the current chunk
        # until we reach overlap_chars, but never go back to `start` so we
        # always advance by at least one paragraph.
        accumulated = 0
        next_start = end
        while next_start > start + 1:
            candidate_len = len(paragraphs[next_start - 1]) + 2
            if accumulated + candidate_len > overlap_chars:
                break
            accumulated += candidate_len
            next_start -= 1

        start = next_start

    _merge_short_tail(chunks)
    return chunks


def _merge_short_tail(chunks: list[dict]) -> None:
    """Merge trailing under-sized chunks into the preceding chunk in-place.

    A tail chunk below MIN_CHARS adds almost no standalone retrieval value and
    inflates the chunk count.  Merging it keeps the last chunk within a
    reasonable size while ensuring every chunk has enough context to be useful.
    Runs in a loop so multiple consecutive tiny tail chunks are all absorbed.
    """
    while len(chunks) >= 2 and chunks[-1]["char_count"] < MIN_CHARS:
        prev = chunks[-2]
        tail = chunks[-1]
        merged = prev["text"] + "\n\n" + tail["text"]
        chunks[-2] = {
            **prev,
            "text": merged,
            "char_count": len(merged),
            "approx_tokens": len(merged) // _CHARS_PER_TOKEN,
        }
        chunks.pop()


def main():
    json_files = sorted(DOCUMENTS_DIR.glob("*.json"))
    print(f"Chunking {len(json_files)} documents\n")
    print(f"  Target:  {TARGET_TOKENS} tokens (~{TARGET_CHARS} chars)")
    print(f"  Overlap: {OVERLAP_TOKENS} tokens (~{OVERLAP_CHARS} chars)\n")

    all_chunks: list[dict] = []

    for path in json_files:
        doc = json.loads(path.read_text(encoding="utf-8"))

        if doc.get("fetch_error"):
            print(f"[SKIP]  {path.name} — fetch error")
            continue

        text = doc.get("cleaned_text") or doc.get("raw_text", "")
        if not text:
            print(f"[SKIP]  {path.name} — no text")
            continue

        doc_id = path.stem
        chunks = chunk_text(
            text=text,
            property_name=doc["property_name"],
            source_url=doc["url"],
            doc_id=doc_id,
        )
        all_chunks.extend(chunks)

        sizes = [c["approx_tokens"] for c in chunks]
        avg = sum(sizes) // len(sizes) if sizes else 0
        print(
            f"[OK]  {path.name}  ->  {len(chunks)} chunks  "
            f"(min {min(sizes)}, avg {avg}, max {max(sizes)} tokens)"
        )

    CHUNKS_PATH.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nSaved {len(all_chunks)} total chunks -> {CHUNKS_PATH.name}")


if __name__ == "__main__":
    main()
