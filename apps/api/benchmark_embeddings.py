import time
import os
import sys

# Ensure app is in path
sys.path.insert(0, "/app")

from app.modules.retrieval.embeddings import get_embedding_provider
from app.core.config import settings
import torch

def generate_mock_text(num_words=90):
    # ~90 words ~ 100 tokens roughly
    word = "benchmark "
    return word * num_words

def run_benchmark():
    print(f"=== BENCHMARK START ===")
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    
    provider = get_embedding_provider()
    
    batch_sizes = [8, 16, 32]
    num_chunks = 320 # easily divisible by all
    
    texts = [generate_mock_text() for _ in range(num_chunks)]
    
    for bz in batch_sizes:
        print(f"\n--- Testing Batch Size: {bz} ---")
        provider.batch_size = bz
        
        # Warmup
        provider.embed_documents(texts[:bz])
        
        start_time = time.time()
        
        provider.embed_documents(texts)
        
        end_time = time.time()
        
        duration = end_time - start_time
        chunks_per_sec = num_chunks / duration
        
        print(f"Total Time: {duration:.2f} s")
        print(f"Throughput: {chunks_per_sec:.2f} chunks/sec")
        
    print("\n=== BENCHMARK END ===")

if __name__ == "__main__":
    run_benchmark()
