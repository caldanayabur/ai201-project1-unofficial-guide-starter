"""
Milestone 4 — Embedding + Vector Store + Retrieval

Pipeline position (see planning.md Architecture diagram):
    Ingestion -> Chunking -> [Embedding + Vector Store] -> [Retrieval] -> Generation
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                              this file

What it does, per the Retrieval Approach section of planning.md:
  1. Loads the chunks produced by chunk.py (chunks.json).
  2. Embeds every chunk with all-MiniLM-L6-v2 (sentence-transformers, runs
     locally, no API key).
  3. Stores the embeddings in ChromaDB with metadata for attribution:
     the source document name and the chunk's position within that document
     (plus property_name and source_url for the generation step later).
  4. Exposes retrieve(query, k) -> top-k chunks + their source info.

Run `python embed.py` to (re)build the index and print a retrieval smoke test
against the evaluation-plan queries.
"""

import json
import sys
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# Some chunks still carry non-ASCII leftovers (curly quotes, icon-font glyphs)
# from the source pages. The Windows console defaults to cp1252 and would crash
# on those when we print a chunk in full, so force UTF-8 output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
CHUNKS_PATH = ROOT / "chunks.json"
CHROMA_DIR = ROOT / "chroma_db"          # persistent on-disk store (gitignored)

MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME = "housing_amenities"
TOP_K = 5    # planning.md started at 4; bumped to 5 after testing — the chunk
             # holding The Standard's amenity list ranked #5, just outside k=4.

# We tell Chroma to use cosine distance instead of its default (squared L2).
# Cosine distance lands in roughly [0, 2] and, for normalized sentence
# embeddings, behaves like the 0=identical / higher=less-similar scale the
# evaluation rubric refers to (good matches well under ~0.5, weak matches
# above ~0.6-0.7). Squared-L2 distances are not bounded that way and would
# make those threshold numbers meaningless.
DISTANCE_SPACE = "cosine"


# --- one shared model + client, loaded lazily so importing this module is cheap.
_model: SentenceTransformer | None = None
_client: chromadb.api.ClientAPI | None = None


def get_model() -> SentenceTransformer:
    """Load the embedding model once and reuse it."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_client() -> "chromadb.api.ClientAPI":
    """A PersistentClient writes the index to disk so we don't re-embed every run."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def load_chunks() -> list[dict]:
    """Read the chunks written by chunk.py."""
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(
            f"{CHUNKS_PATH.name} not found. Run `python chunk.py` first."
        )
    return json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))


def build_index() -> "chromadb.api.models.Collection.Collection":
    """
    Embed all chunks and (re)load them into ChromaDB.

    We delete and recreate the collection so repeated runs don't pile up
    duplicate entries. Each chunk is stored with:
      - id:        chunk_id (stable, unique)
      - document:  the chunk text
      - embedding: the all-MiniLM-L6-v2 vector
      - metadata:  source_doc + chunk position (+ property_name, source_url)
    """
    chunks = load_chunks()
    model = get_model()
    client = get_client()

    # Fresh collection every build -> no stale or duplicated vectors.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # didn't exist yet — fine.
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": DISTANCE_SPACE},
    )

    texts = [c["text"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]

    # Embed a property-tagged version of each chunk, not the bare text.
    # Many chunks are bare amenity lists with no property name in them, so a
    # query like "amenities at The Standard" would match generic intro chunks
    # (which DO contain the name) over the chunk that actually holds the
    # amenities. Prepending the property name injects that identity into the
    # vector so retrieval stays specific to the right complex. We still store
    # the clean original text as the document for display/attribution.
    embed_texts = [f"{c['property_name']}\n\n{c['text']}" for c in chunks]

    # Track each chunk's position within its own source document. chunk.py
    # emits chunks in document order, so a per-doc counter gives the position.
    position_in_doc: dict[str, int] = {}
    metadatas = []
    for c in chunks:
        doc = c["doc_id"]
        pos = position_in_doc.get(doc, 0)
        position_in_doc[doc] = pos + 1
        metadatas.append({
            "source_doc": doc,                  # source document name (attribution)
            "chunk_position": pos,              # position within that document
            "property_name": c["property_name"],
            "source_url": c["source_url"],
        })

    print(f"Embedding {len(texts)} chunks with {MODEL_NAME} ...")
    embeddings = model.encode(embed_texts, show_progress_bar=True).tolist()

    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    print(f"Stored {collection.count()} chunks in collection '{COLLECTION_NAME}'.")
    return collection


def get_collection() -> "chromadb.api.models.Collection.Collection":
    """Open the existing collection, building it if this is a first run."""
    client = get_client()
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        print("No existing index found — building it now.")
        return build_index()


def retrieve(query: str, k: int = TOP_K) -> list[dict]:
    """
    Retrieve the top-k most relevant chunks for a query.

    Returns a list (best match first) of dicts:
        {
          "text":           full chunk text,
          "distance":       cosine distance (0 = identical, higher = less similar),
          "source_doc":     source document name,
          "chunk_position": position of the chunk within that document,
          "property_name":  apartment/property the chunk is about,
          "source_url":     original page URL (for attribution),
        }
    """
    model = get_model()
    collection = get_collection()

    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=k,
    )

    # Chroma returns parallel lists wrapped in an outer list (one per query).
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]

    return [
        {
            "text": doc,
            "distance": dist,
            "source_doc": meta["source_doc"],
            "chunk_position": meta["chunk_position"],
            "property_name": meta["property_name"],
            "source_url": meta["source_url"],
        }
        for doc, meta, dist in zip(docs, metas, dists)
    ]


# --- Retrieval smoke test ----------------------------------------------------
# The 5 evaluation-plan queries from planning.md. For each we print the
# returned chunks with their distance scores so we can judge relevance.
TEST_QUERIES = [
    "Which amenities does The Standard at Tampa highlight?",
    "What features does Halo 46 list on its amenities page?",
    "What amenities are featured for Hub On Campus Tampa?",
    "What does 4050 Lofts showcase on its amenities page?",
    "What amenities are listed for Venue at North Campus?",
]


def _preview(text: str, n: int = 220) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= n else flat[:n] + " ..."


def smoke_test() -> None:
    print("\n" + "=" * 78)
    print("RETRIEVAL SMOKE TEST  (top-k =", TOP_K, ")")
    print("=" * 78)
    for query in TEST_QUERIES:
        print(f"\nQuery: {query!r}")
        print("-" * 78)
        for rank, hit in enumerate(retrieve(query), start=1):
            print(
                f"  #{rank}  distance={hit['distance']:.3f}  "
                f"source={hit['source_doc']} (chunk {hit['chunk_position']})  "
                f"property={hit['property_name']}"
            )
            print(f"        {_preview(hit['text'])}")
        # Print the single best chunk in full — makes it easy to debug whether a
        # match is genuinely relevant or just shares a few words with the query.
        best = retrieve(query, k=1)[0]
        print(f"\n  >> full text of top result (distance {best['distance']:.3f}):")
        print("     " + best["text"].replace("\n", "\n     "))


if __name__ == "__main__":
    build_index()
    smoke_test()
