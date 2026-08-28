import os
from typing import List, Dict, Any, Optional
from pinecone import Pinecone
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config import settings

# Initialize Pinecone
pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY", ""))
index_name = "merchant-maxx"

# gemini-embedding-001 outputs 3072 dimensions
EMBEDDING_DIMENSION = 3072

# Initialize Google Embeddings
embeddings = None
try:
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001", 
        google_api_key=settings.LLM_API_KEY
    )
except Exception as e:
    print(f"Failed to initialize embeddings: {e}")

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

def get_product_embedding(text: str) -> List[float]:
    """Get embedding for a text string"""
    if not embeddings:
        return []
    return embeddings.embed_query(text)

def search_products_vector(query: str, top_k: int = 5, category: Optional[str] = None, namespace: str = "") -> List[Dict[str, Any]]:
    """Search for products using semantic vector search.
    Falls back to empty results if Pinecone or embeddings are unavailable."""
    if not pinecone_index or not embeddings:
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
    if not pinecone_index or not embeddings:
        return
        
    try:
        embedding = get_product_embedding(text_content)
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
