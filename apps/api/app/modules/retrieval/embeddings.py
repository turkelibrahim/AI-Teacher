import logging
from typing import List
from sentence_transformers import SentenceTransformer
from app.core.config import settings
import torch

logger = logging.getLogger("canli_ogretmen.retrieval.embeddings")

class EmbeddingProvider:
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> List[float]:
        raise NotImplementedError

class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        self.device = settings.EMBEDDING_DEVICE
        self.batch_size = settings.EMBEDDING_BATCH_SIZE
        
        # Enforce CPU policy for this project phase
        if self.device != "cpu":
            logger.warning(f"Configured device is {self.device}, but forcing to 'cpu' as per Phase 5 policy.")
            self.device = "cpu"

        logger.info(f"Loading local embedding model: {self.model_name} on {self.device}")
        
        # Additional PyTorch checks for logging evidence
        logger.info(f"PyTorch CUDA available: {torch.cuda.is_available()}")

        try:
            self.model = SentenceTransformer(self.model_name, device=self.device)
        except Exception as e:
            logger.error(f"Failed to load sentence-transformers model {self.model_name}: {e}")
            raise

        # Validate dimension matches config
        actual_dim = self.model.get_sentence_embedding_dimension()
        if actual_dim != settings.EMBEDDING_DIMENSION:
            raise ValueError(f"Dimension mismatch: configured {settings.EMBEDDING_DIMENSION}, model returned {actual_dim}")
            
        # Validate effective maximum sequence length matches our config chunk max
        max_seq = self.model.max_seq_length
        if settings.CHUNK_MAX_TOKENS > max_seq:
            raise ValueError(f"CHUNK_MAX_TOKENS ({settings.CHUNK_MAX_TOKENS}) exceeds model max_seq_length ({max_seq}). Silent truncation would occur.")
        
        logger.info(f"Model loaded successfully. Dimension: {actual_dim}, Max Sequence Length: {max_seq}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        # Enforce conversion to float32 lists
        embeddings = self.model.encode(texts, batch_size=self.batch_size, convert_to_numpy=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        if not text:
            return []
        embedding = self.model.encode([text], convert_to_numpy=True)
        return embedding[0].tolist()

def get_embedding_provider() -> EmbeddingProvider:
    return LocalEmbeddingProvider()
