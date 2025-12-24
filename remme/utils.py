import requests
import numpy as np
import sys

# Configuration matches server_rag.py for consistency
EMBED_URL = "http://127.0.0.1:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"
OLLAMA_TIMEOUT = 300

def get_embedding(text: str) -> np.ndarray:
    """Generate embedding for text using local Ollama instance."""
    try:
        response = requests.post(
            EMBED_URL, 
            json={"model": EMBED_MODEL, "prompt": text}, 
            timeout=OLLAMA_TIMEOUT
        )
        response.raise_for_status()
        embedding = response.json()["embedding"]
        return np.array(embedding, dtype=np.float32)
    except Exception as e:
        print(f"Error generating embedding: {e}", file=sys.stderr)
        return np.zeros(768, dtype=np.float32) # Fallback to empty vector
