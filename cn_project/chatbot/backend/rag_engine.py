"""
rag_engine.py
=============
Handles the RETRIEVAL half of RAG (Retrieval Augmented Generation).

When a student uploads notes, we split them into small chunks and store
them. When a question comes in, we find the chunks most similar in
meaning to the question and hand them to the LLM as context, so answers
can be grounded in the student's OWN notes instead of pure guesswork.

We use TF-IDF + cosine similarity (from scikit-learn) rather than a
neural embedding model. This is a deliberate choice for reliability: it
needs no external model download, no GPU, and no network call, so it
works instantly and identically every time - important for a student
project that needs to demo reliably. TF-IDF is a well-established,
explainable retrieval technique in its own right (it's what search
engines used for decades before neural embeddings became common), so
it's a legitimate and defensible design choice, not just a workaround.

Notes are stored per-student (student_id) in a simple JSON file, so
students never see each other's notes.
"""

import os
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

STORE_PATH = os.path.join(os.path.dirname(__file__), "notes_store.json")


def _load_store() -> dict:
    if not os.path.exists(STORE_PATH):
        return {}
    with open(STORE_PATH, "r") as f:
        return json.load(f)


def _save_store(store: dict):
    with open(STORE_PATH, "w") as f:
        json.dump(store, f)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50):
    """Splits text into overlapping chunks. Overlap helps avoid losing
    context that straddles a chunk boundary."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]


def add_notes(student_id: str, source_name: str, text: str) -> int:
    """Chunks and stores a document's text under a given student_id.
    Returns the number of chunks stored."""
    chunks = chunk_text(text)
    if not chunks:
        return 0

    store = _load_store()
    store.setdefault(student_id, [])
    for i, chunk in enumerate(chunks):
        store[student_id].append({"source": source_name, "chunk_index": i, "text": chunk})
    _save_store(store)
    return len(chunks)


def retrieve_relevant_chunks(student_id: str, question: str, n_results: int = 3):
    """Finds the chunks most relevant to `question` using TF-IDF cosine
    similarity, restricted to this student's own notes only."""
    store = _load_store()
    chunks = store.get(student_id, [])
    if not chunks:
        return []

    texts = [c["text"] for c in chunks]
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform(texts + [question])
    except ValueError:
        return []  # e.g. all-stopword content, nothing meaningful to compare

    question_vector = matrix[-1]
    chunk_vectors = matrix[:-1]
    similarities = cosine_similarity(question_vector, chunk_vectors)[0]

    ranked = sorted(zip(similarities, texts), key=lambda x: -x[0])
    top = [text for score, text in ranked[:n_results] if score > 0.05]
    return top


def clear_student_notes(student_id: str):
    """Removes all stored notes for a student (e.g. if they want a clean slate)."""
    store = _load_store()
    store.pop(student_id, None)
    _save_store(store)