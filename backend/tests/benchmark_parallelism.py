"""
Task 18 — Performance benchmark for Scout vs Booster parallelism.
"""
import time
import statistics
import sys
from unittest.mock import patch, MagicMock

# Mock pinecone initialization before importing maxx_app
patch('pinecone.Pinecone', MagicMock()).start()

from langchain_core.messages import HumanMessage, AIMessage
from agents.maxx import maxx_app

def simulate_llm_delay(delay_sec: float):
    def _invoke(*args, **kwargs):
        time.sleep(delay_sec)
        return AIMessage(content="Mocked response")
    
    mock_inst = MagicMock()
    mock_inst.invoke.side_effect = _invoke
    mock_inst.bind_tools.return_value = mock_inst
    
    mock_get_llm = MagicMock(return_value=mock_inst)
    return mock_get_llm

def run_benchmark():
    print("--- Task 18 Performance Benchmark ---")
    
    # We mock LLM to take exactly 1.0 seconds.
    # In parallel, total time should be ~1.0 seconds.
    # In sequential, it would be ~2.0 seconds.
    
    runs = 5
    latencies = []
    
    print(f"Running {runs} simulated parallel graph iterations (Scout + Booster)...")
    
    for i in range(runs):
        with patch("agents.scout.get_llm", simulate_llm_delay(1.0)), \
             patch("agents.booster.get_llm", simulate_llm_delay(1.0)):
            
            start_time = time.perf_counter()
            config = {"configurable": {"thread_id": f"bench_{i}"}}
            inputs = {
                "messages": [HumanMessage(content="What accessories are there for this laptop?")],
                "purchase_state": "PRODUCT_SELECTED",
                "purchase_context": {
                    "purchase_intent_id": "pi_test",
                    "basket_items": [{"product_id": "item_laptop_1"}]
                }
            }
            maxx_app.invoke(inputs, config)
            latencies.append(time.perf_counter() - start_time)
            
    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
    
    print(f"\nParallel Graph Latency (1.0s mocked LLMs):")
    print(f"P50: {p50:.3f} s")
    print(f"P95: {p95:.3f} s")
    print(f"Min: {min(latencies):.3f} s")
    print(f"Max: {max(latencies):.3f} s")
    
    # Expectation: Time should be slightly over 1.0s, NOT 2.0s.
    if p50 < 1.5:
        print("\n✅ PASSED: Parallel architecture is working (latency ≈ max(Scout, Booster))")
    else:
        print("\n❌ FAILED: Parallel architecture is blocking sequentially.")

if __name__ == "__main__":
    run_benchmark()
