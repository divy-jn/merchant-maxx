import asyncio
import time
from dotenv import load_dotenv
load_dotenv()
from langchain_core.messages import HumanMessage
from agents.maxx import maxx_app
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_chat_request(conv_id: str, message: str, state: str = "IDLE", context: dict = None):
    inputs = {
        "messages": [HumanMessage(content=message)],
        "session_id": conv_id,
        "customer_id": "test_user",
        "purchase_state": state,
        "purchase_context": context or {},
        "user_confirmed": False
    }
    config = {"configurable": {"thread_id": conv_id}, "recursion_limit": 10}
    start = time.perf_counter()
    try:
        # We use ainvoke for true concurrency
        res = await maxx_app.ainvoke(inputs, config)
        return {"success": True, "duration": time.perf_counter() - start, "result": res}
    except Exception as e:
        return {"success": False, "duration": time.perf_counter() - start, "error": str(e)}

async def run_benchmark(concurrency: int, message: str):
    tasks = []
    for i in range(concurrency):
        tasks.append(run_chat_request(f"bench_{concurrency}_{i}", message))
    
    results = await asyncio.gather(*tasks)
    
    successes = [r for r in results if r["success"]]
    errors = [r for r in results if not r["success"]]
    durations = sorted([r["duration"] for r in successes])
    
    if not durations:
        logger.error(f"Concurrency {concurrency}: 100% Error Rate. Errors: {[e['error'] for e in errors]}")
        return
        
    p50 = durations[len(durations)//2]
    p95 = durations[int(len(durations)*0.95)] if len(durations) >= 20 else durations[-1]
    
    logger.info(f"--- Benchmark {concurrency} concurrent requests ---")
    logger.info(f"Message: {message}")
    logger.info(f"Success: {len(successes)}, Errors: {len(errors)}")
    logger.info(f"Min: {durations[0]:.2f}s, Max: {durations[-1]:.2f}s, P50: {p50:.2f}s, P95: {p95:.2f}s")
    if errors:
        logger.info(f"Sample error: {errors[0]['error']}")
    return {"success_rate": len(successes)/concurrency, "p50": p50}

if __name__ == "__main__":
    asyncio.run(run_benchmark(1, "Hi there"))
    asyncio.run(run_benchmark(2, "Show me laptops"))
    # asyncio.run(run_benchmark(5, "What phones do you have?"))
