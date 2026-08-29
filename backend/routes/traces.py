from fastapi import APIRouter, HTTPException, Depends
from langsmith import Client
from config import settings
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/traces", tags=["traces"])

try:
    # Requires LANGSMITH_API_KEY in environment
    client = Client()
except:
    client = None

@router.get("/latest")
def get_latest_traces(limit: int = 10, current_user: dict = Depends(get_current_user)):
    """Fetch the latest Agent traces from LangSmith for the frontend Trace Viewer"""
    if not client:
        raise HTTPException(status_code=503, detail="LangSmith client not initialized. Check LANGSMITH_API_KEY.")
    
    try:
        # Fetch latest runs for the 'merchant-maxx' project
        runs = client.list_runs(
            project_name=getattr(settings, 'LANGCHAIN_PROJECT', 'merchant-maxx'),
            execution_order=1, # Only get root runs (the full trace)
            limit=limit,
            order="desc"
        )
        
        trace_data = []
        for run in runs:
            trace_data.append({
                "id": str(run.id),
                "name": run.name,
                "status": run.status,
                "start_time": run.start_time.isoformat() if run.start_time else None,
                "end_time": run.end_time.isoformat() if run.end_time else None,
                "latency_ms": (run.end_time - run.start_time).total_seconds() * 1000 if run.end_time and run.start_time else 0,
                "tokens": run.prompt_tokens + run.completion_tokens if hasattr(run, 'prompt_tokens') and run.prompt_tokens else 0,
                "error": run.error
            })
            
        return trace_data
    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")
