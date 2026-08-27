from typing import Any, Dict, List
from search.vector_store import pinecone_index, embeddings

KNOWLEDGE_NAMESPACE = "knowledge"

def _embed(text: str) -> List[float]:
    if not embeddings:
        return []
    return embeddings.embed_query(text)

def upsert_knowledge(doc_id: str, text: str, metadata: Dict[str, Any] | None = None) -> bool:
    """Store merchant policy/FAQ knowledge separately from product vectors."""
    if not pinecone_index:
        return False
    vector = _embed(text)
    if not vector:
        return False
    pinecone_index.upsert(vectors=[{"id": str(doc_id), "values": vector, "metadata": metadata or {"text": text}}], namespace=KNOWLEDGE_NAMESPACE)
    return True

def search_knowledge(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    if not pinecone_index:
        return []
    vector = _embed(query)
    if not vector:
        return []
    result = pinecone_index.query(vector=vector, top_k=top_k, include_metadata=True, namespace=KNOWLEDGE_NAMESPACE)
    return [{"id": m.id, "score": m.score, **(m.metadata or {})} for m in result.matches]
