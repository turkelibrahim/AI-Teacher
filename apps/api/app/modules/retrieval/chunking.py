import re
import logging
from transformers import AutoTokenizer
from app.core.config import settings

logger = logging.getLogger("canli_ogretmen.retrieval.chunking")

class SemanticChunker:
    def __init__(self, target_tokens: int = 96, max_tokens: int = 112, overlap_tokens: int = 16):
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        try:
            # We use the embedding model's tokenizer directly
            self.tokenizer = AutoTokenizer.from_pretrained(settings.EMBEDDING_MODEL)
        except Exception as e:
            logger.error(f"Failed to load tokenizer for {settings.EMBEDDING_MODEL}: {e}")
            raise

    def get_token_count(self, text: str) -> int:
        if not text:
            return 0
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def decode_tokens(self, tokens: list[int]) -> str:
        return self.tokenizer.decode(tokens, clean_up_tokenization_spaces=True)

    def chunk_text(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        # 1. Split by paragraphs
        paragraphs = re.split(r'\n\s*\n', text)
        
        chunks = []
        current_chunk_texts = []
        current_tokens = 0
        
        def add_chunk(chunk_texts):
            if not chunk_texts:
                return
            combined = "\n\n".join(chunk_texts).strip()
            if combined:
                # Absolute guard: if somehow combined exceeds max_tokens, forcefully split it
                c_tokens = self.get_token_count(combined)
                if c_tokens > self.max_tokens:
                    logger.warning(f"Combined chunk exceeded max_tokens ({c_tokens} > {self.max_tokens}), forcing strict token split.")
                    encoded = self.tokenizer.encode(combined, add_special_tokens=False)
                    start = 0
                    while start < len(encoded):
                        end = min(start + self.max_tokens, len(encoded))
                        chunks.append(self.decode_tokens(encoded[start:end]))
                        start += self.max_tokens - self.overlap_tokens
                else:
                    chunks.append(combined)

        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
                
            p_tokens = self.get_token_count(p)
            
            # If a single paragraph is larger than max_tokens, split it by sentences.
            if p_tokens > self.max_tokens:
                add_chunk(current_chunk_texts)
                current_chunk_texts = []
                current_tokens = 0
                
                # Split by sentences using standard punctuation heuristics
                sentences = re.split(r'(?<=[.!?])\s+', p)
                for s in sentences:
                    s = s.strip()
                    if not s:
                        continue
                    s_tokens = self.get_token_count(s)
                    
                    # If a single sentence is larger than max_tokens, fallback to strict token split
                    if s_tokens > self.max_tokens:
                        add_chunk(current_chunk_texts)
                        current_chunk_texts = []
                        current_tokens = 0
                        
                        encoded = self.tokenizer.encode(s, add_special_tokens=False)
                        start = 0
                        while start < len(encoded):
                            end = min(start + self.max_tokens, len(encoded))
                            chunks.append(self.decode_tokens(encoded[start:end]))
                            start += self.max_tokens - self.overlap_tokens
                    else:
                        if current_tokens + s_tokens > self.target_tokens and current_tokens > 0:
                            add_chunk(current_chunk_texts)
                            
                            # Overlap logic
                            overlap_texts = []
                            overlap_tokens_count = 0
                            for prev_s in reversed(current_chunk_texts):
                                t = self.get_token_count(prev_s)
                                if overlap_tokens_count + t <= self.overlap_tokens:
                                    overlap_texts.insert(0, prev_s)
                                    overlap_tokens_count += t
                                else:
                                    break
                            current_chunk_texts = overlap_texts + [s]
                            current_tokens = overlap_tokens_count + s_tokens
                        else:
                            current_chunk_texts.append(s)
                            current_tokens += s_tokens
                            
            else:
                if current_tokens + p_tokens > self.target_tokens and current_tokens > 0:
                    add_chunk(current_chunk_texts)
                    
                    # Overlap logic across paragraphs
                    overlap_texts = []
                    overlap_tokens_count = 0
                    for prev_p in reversed(current_chunk_texts):
                        t = self.get_token_count(prev_p)
                        if overlap_tokens_count + t <= self.overlap_tokens:
                            overlap_texts.insert(0, prev_p)
                            overlap_tokens_count += t
                        else:
                            break
                    current_chunk_texts = overlap_texts + [p]
                    current_tokens = overlap_tokens_count + p_tokens
                else:
                    current_chunk_texts.append(p)
                    current_tokens += p_tokens
                    
        # Add any remaining
        if current_chunk_texts:
            add_chunk(current_chunk_texts)
            
        return chunks
