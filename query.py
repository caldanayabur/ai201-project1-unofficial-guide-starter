"""
Milestone 5 — Grounded Generation

Pipeline position (see planning.md Architecture diagram):
    Ingestion -> Chunking -> Embedding + Vector Store -> [Retrieval] -> [Generation]
                                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                          retrieval from embed.py,
                                                          generation here

What it does:
  1. Retrieves the top-k relevant chunks for a question (embed.retrieve()).
  2. Builds a context block from ONLY those chunks, each labelled with its
     source so the model can attribute claims.
  3. Asks Groq's llama-3.3-70b-versatile to answer using ONLY that context,
     under a system prompt that *forbids* falling back on training knowledge.
  4. Returns {"answer": str, "sources": list[str]} where `sources` is built
     programmatically from the retrieved chunks — it is NOT parsed out of the
     model's text, so attribution is guaranteed rather than hoped for.

Grounding is enforced three ways:
  - A relevance gate: if even the best chunk is too far from the query, we
    never call the LLM and return the "not enough information" message.
  - A system prompt that requires the answer to come from the context only and
    to use a fixed refusal sentence when the context doesn't cover the question.
  - Sources attached in Python from retrieval metadata; when the model refuses,
    we drop the sources so a refusal can't appear "cited".

Run `python query.py` for an end-to-end grounding test against the evaluation
queries plus one deliberately out-of-domain question.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from embed import retrieve, TOP_K

# Source pages carry curly quotes / glyphs; keep console output UTF-8 on Windows.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(Path(__file__).parent / ".env")

MODEL = "llama-3.3-70b-versatile"   # Groq free-tier, OpenAI-compatible chat model.

# The fixed sentence the model must use when the context doesn't answer the
# question. We match on this in code to decide whether to attach sources.
INSUFFICIENT = "I don't have enough information on that."

# Relevance gate. Cosine distances for this corpus (see embed.py) run well under
# ~0.5 for good matches and ~0.6-0.7 for weak ones; clearly off-topic queries
# land much higher. If the *best* retrieved chunk is past this, we treat the
# question as out of domain and refuse before spending an LLM call — this is the
# hard backstop for "ask something the documents don't cover".
RELEVANCE_THRESHOLD = 0.9

SYSTEM_PROMPT = (
    "You are The Unofficial Guide, a question-answering assistant for off-campus "
    "student housing near the USF Tampa campus.\n\n"
    "STRICT GROUNDING RULES — follow them exactly:\n"
    "1. Answer using ONLY the information in the CONTEXT section of the user "
    "message. The context is the sole source of truth.\n"
    "2. Do NOT use any prior or general knowledge about apartments, amenities, "
    "Tampa, or these properties. If a fact is not in the context, you do not "
    "know it.\n"
    "3. If the context does not contain enough information to answer the "
    f"question, reply with exactly this sentence and nothing else: \"{INSUFFICIENT}\"\n"
    "4. Do not speculate, generalize, or add caveats drawn from outside the "
    "context. Do not invent property names, amenities, or details.\n"
    "5. The context may contain chunks from several different properties. Each "
    "chunk is labelled with its property. Attribute an amenity to a property "
    "ONLY if it appears in a chunk labelled with that same property. Never mix "
    "amenities from one property into the answer for another.\n"
    "6. Keep the answer concise and factual, naming the specific property and "
    "amenities the context supports.\n"
    "Sources are attached to the response automatically, so you do not need to "
    "list URLs or file names yourself."
)


# One reusable client, created lazily so importing this module doesn't require a
# key just to be imported (the UI imports `ask`, but tests may import only this).
_client: Groq | None = None


def get_client() -> Groq:
    """Create the Groq client once, reading GROQ_API_KEY from the environment."""
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key or api_key == "your_key_here":
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your "
                "free key from https://console.groq.com"
            )
        _client = Groq(api_key=api_key)
    return _client


def _format_context(hits: list[dict]) -> str:
    """
    Render retrieved chunks into a numbered context block.

    Each chunk is tagged with its property and source document so the model can
    ground its answer in a specific source, and so a reader can trace any claim
    back to the chunk it came from.
    """
    blocks = []
    for i, hit in enumerate(hits, start=1):
        blocks.append(
            f"[{i}] Property: {hit['property_name']} "
            f"(source: {hit['source_doc']})\n{hit['text']}"
        )
    return "\n\n".join(blocks)


def _source_labels(hits: list[dict]) -> list[str]:
    """
    Build the human-readable source list straight from retrieval metadata.

    De-duplicated, best-match order preserved. This is what guarantees source
    attribution: it is derived from the chunks we actually retrieved, never from
    the model's free text.
    """
    labels: list[str] = []
    for hit in hits:
        label = f"{hit['property_name']} — {hit['source_doc']} ({hit['source_url']})"
        if label not in labels:
            labels.append(label)
    return labels


def ask(question: str, k: int = TOP_K) -> dict:
    """
    Answer a question, grounded strictly in the retrieved housing documents.

    Returns:
        {
          "answer":  str,         # grounded answer, or the refusal sentence
          "sources": list[str],   # attribution for the chunks used (empty on refusal)
        }
    """
    question = (question or "").strip()
    if not question:
        return {"answer": "Please enter a question.", "sources": []}

    hits = retrieve(question, k=k)

    # Hard relevance backstop: nothing close enough -> refuse without an LLM call.
    if not hits or hits[0]["distance"] > RELEVANCE_THRESHOLD:
        return {"answer": INSUFFICIENT, "sources": []}

    context = _format_context(hits)
    user_message = (
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        "Answer using only the context above."
    )

    response = get_client().chat.completions.create(
        model=MODEL,
        temperature=0,        # deterministic, no creative drift away from context
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    answer = response.choices[0].message.content.strip()

    # If the model refused, don't attach sources — a refusal isn't "from" a doc.
    if INSUFFICIENT.rstrip(".").lower() in answer.lower():
        return {"answer": INSUFFICIENT, "sources": []}

    return {"answer": answer, "sources": _source_labels(hits)}


# --- End-to-end grounding test ----------------------------------------------
# The 5 evaluation-plan queries plus one out-of-domain question. The grounding
# test: every answer must be traceable to the cited chunks, and the off-topic
# question must return the refusal sentence with no sources.
TEST_QUERIES = [
    "Which amenities does The Standard at Tampa highlight?",
    "What features does Halo 46 list on its amenities page?",
    "What amenities are featured for Hub On Campus Tampa?",
    "What does 4050 Lofts showcase on its amenities page?",
    "What amenities are listed for Venue at North Campus?",
    "What is the best pizza restaurant in downtown Chicago?",  # out of domain
]


def _grounding_test() -> None:
    print("\n" + "=" * 78)
    print("GROUNDED GENERATION TEST")
    print("=" * 78)
    for q in TEST_QUERIES:
        result = ask(q)
        print(f"\nQ: {q}")
        print(f"A: {result['answer']}")
        if result["sources"]:
            print("Sources:")
            for s in result["sources"]:
                print(f"  • {s}")
        else:
            print("Sources: (none)")


if __name__ == "__main__":
    _grounding_test()
