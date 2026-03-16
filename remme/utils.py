import requests
import numpy as np
import sys
from pathlib import Path

# Import from centralized settings
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings_loader import get_ollama_url, get_model, get_timeout

EMBED_URL = get_ollama_url("embed")
EMBED_MODEL = get_model("embedding")
OLLAMA_TIMEOUT = get_timeout()
# Must match Qdrant collection dimension (e.g. arcturus_memories, arcturus_episodic)
EMBEDDING_DIM = 768

def get_embedding(text: str, task_type: str = "search_document") -> np.ndarray:
    """Generate embedding for text using local Ollama instance with Nomic prefixes."""
    try:
        # 🏷️ Nomic Embed v1.5 requires task-specific prefixes
        # search_query: for the query
        # search_document: for the facts/documents
        prefix = f"{task_type}: "
        full_text = prefix + text if not text.startswith(prefix) else text

        response = requests.post(
            EMBED_URL,
            json={"model": EMBED_MODEL, "input": full_text},
            timeout=OLLAMA_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        # Ollama /api/embed returns "embeddings" (array of vectors). OpenAI-compatible APIs use "data"[0]["embedding"].
        embedding = None
        if data.get("embeddings") and len(data["embeddings"]) > 0:
            embedding = data["embeddings"][0]
        elif data.get("data") and len(data["data"]) > 0:
            embedding = data["data"][0].get("embedding", [])
        if embedding is None:
            embedding = data.get("embedding", [])
        vec = np.array(embedding, dtype=np.float32)
        if vec.size == 0 or len(vec) != EMBEDDING_DIM:
            print(
                f"⚠️ Embedding API returned invalid vector (size={vec.size}, expected dim={EMBEDDING_DIM}). "
                f"Model={EMBED_MODEL}. Ensure the embedding model is loaded: ollama pull {EMBED_MODEL.split(':')[0]}",
                file=sys.stderr,
            )
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)

        # 📐 L2 Normalization (ensures distances are in [0, 4] range for IndexFlatL2)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        return vec
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
        # Re-raise connection issues so the caller can decide to abort/pause
        # This prevents spamming logs if Ollama is down
        print(f"⚠️ Ollama Connection Error: {e}", file=sys.stderr)
        raise e
    except Exception as e:
        print(f"Error generating embedding: {e}", file=sys.stderr)
        return np.zeros(EMBEDDING_DIM, dtype=np.float32)
