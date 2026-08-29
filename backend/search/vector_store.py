import os
from typing import List, Dict, Any, Optional
from pinecone import Pinecone
from config import settings

# Initialize Pinecone
pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY", ""))
index_name = "merchant-maxx-v2"
EMBEDDING_MODEL = "multilingual-e5-large"
EMBEDDING_DIMENSION = 1024

def init_pinecone():
    """Ensure the index exists with correct dimensions"""
    try:
        existing_indexes = [index_info["name"] for index_info in pc.list_indexes()]
        if index_name not in existing_indexes:
            print(f"Creating Pinecone index: {index_name} (dim={EMBEDDING_DIMENSION})")
            pc.create_index(
                name=index_name,
                dimension=EMBEDDING_DIMENSION,
                metric="cosine",
                spec={"serverless": {"cloud": "aws", "region": "us-east-1"}}
            )
        else:
            # Verify dimension matches; if not, delete and recreate
            idx = pc.Index(index_name)
            stats = idx.describe_index_stats()
            current_dim = stats.dimension
            if current_dim != EMBEDDING_DIMENSION:
                print(f"Pinecone index dimension mismatch: {current_dim} vs {EMBEDDING_DIMENSION}. Deleting and recreating...")
                pc.delete_index(index_name)
                pc.create_index(
                    name=index_name,
                    dimension=EMBEDDING_DIMENSION,
                    metric="cosine",
                    spec={"serverless": {"cloud": "aws", "region": "us-east-1"}}
                )
        return pc.Index(index_name)
    except Exception as e:
        print(f"Pinecone init error: {e}")
        return None

pinecone_index = init_pinecone()

def get_product_embedding(text: str, is_query: bool = True) -> List[float]:
    """Get embedding for a text string using Pinecone Inference"""
    try:
        input_type = "query" if is_query else "passage"
        res = pc.inference.embed(
            model=EMBEDDING_MODEL,
            inputs=[text],
            parameters={"input_type": input_type, "truncate": "END"}
        )
        return res[0].values
    except Exception as e:
        print(f"Embedding error: {e}")
        return []

def search_products_vector(query: str, top_k: int = 5, category: Optional[str] = None, namespace: str = "") -> List[Dict[str, Any]]:
    """Search for products using semantic vector search.
    Falls back to empty results if Pinecone or embeddings are unavailable."""
    if not pinecone_index:
        return []
        
    try:
        query_embedding = get_product_embedding(query)
        if not query_embedding:
            return []
        
        filter_dict = {}
        if category:
            filter_dict["category"] = category
            
        results = pinecone_index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict if filter_dict else None,
            namespace=namespace
        )
        
        # Format results to match our catalog structure
        formatted_results = []
        for match in results.matches:
            formatted_results.append({
                "id": match.id,
                "score": match.score,
                **match.metadata
            })
            
        return formatted_results
    except Exception as e:
        print(f"Pinecone search error: {e}")
        return []

def index_product(product_id: str, text_content: str, metadata: dict, namespace: str = ""):
    """Upsert a product into Pinecone"""
    if not pinecone_index:
        return
        
    try:
        embedding = get_product_embedding(text_content, is_query=False)
        if not embedding:
            return
        pinecone_index.upsert(
            vectors=[{
                "id": str(product_id),
                "values": embedding,
                "metadata": metadata
            }],
            namespace=namespace
        )
    except Exception as e:
        print(f"Pinecone upsert error: {e}")
