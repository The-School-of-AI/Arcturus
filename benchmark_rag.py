import requests
import time
import json

OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "nomic-embed-text"
NUM_CHUNKS = 50
BATCH_SIZE = 10

# Dummy chunks
CHUNKS = [f"This is chunk number {i} with some rigorous semantic content to simulate a real workload." for i in range(NUM_CHUNKS)]

def test_sequential():
    print(f"\n--- Testing Sequential (1 by 1) for {NUM_CHUNKS} chunks ---")
    start_time = time.time()
    
    for i, chunk in enumerate(CHUNKS):
        try:
            res = requests.post(f"{OLLAMA_URL}/api/embeddings", json={
                "model": MODEL,
                "prompt": chunk
            })
            res.raise_for_status()
        except Exception as e:
            print(f"Error on chunk {i}: {e}")
            
    end_time = time.time()
    total_time = end_time - start_time
    print(f"Sequential Time: {total_time:.4f} seconds")
    print(f"Throughput: {NUM_CHUNKS / total_time:.2f} chunks/sec")
    return total_time

def test_batched():
    print(f"\n--- Testing Batched (Batch Size {BATCH_SIZE}) for {NUM_CHUNKS} chunks ---")
    start_time = time.time()
    
    # Split into batches
    batches = [CHUNKS[i:i + BATCH_SIZE] for i in range(0, len(CHUNKS), BATCH_SIZE)]
    
    for batch in batches:
        try:
            # Note: /api/embed expects "input" as a list of strings
            res = requests.post(f"{OLLAMA_URL}/api/embed", json={
                "model": MODEL,
                "input": batch
            })
            res.raise_for_status()
        except Exception as e:
            print(f"Error on batch: {e}")
            
    end_time = time.time()
    total_time = end_time - start_time
    print(f"Batched Time: {total_time:.4f} seconds")
    print(f"Throughput: {NUM_CHUNKS / total_time:.2f} chunks/sec")
    return total_time

if __name__ == "__main__":
    print(f"Benchmarking Embeddings with Model: {MODEL}")
    
    # Warmup
    print("Warming up model...")
    requests.post(f"{OLLAMA_URL}/api/embeddings", json={"model": MODEL, "prompt": "warmup"})
    
    seq_time = test_sequential()
    batch_time = test_batched()
    
    speedup = seq_time / batch_time
    print(f"\n🚀 Speedup: {speedup:.2f}x")
    
    with open("benchmark_results.txt", "w") as f:
        f.write(f"Sequential: {seq_time:.4f}s\n")
        f.write(f"Batched: {batch_time:.4f}s\n")
        f.write(f"Speedup: {speedup:.2f}x\n")
