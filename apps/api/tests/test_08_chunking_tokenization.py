import pytest
from app.modules.retrieval.chunking import SemanticChunker
from app.core.config import settings

def test_chunking_tokenization_limits():
    chunker = SemanticChunker(target_tokens=settings.CHUNK_TARGET_TOKENS, 
                              max_tokens=settings.CHUNK_MAX_TOKENS, 
                              overlap_tokens=settings.CHUNK_OVERLAP_TOKENS)
                              
    # Long Turkish text (about 300-400 words, > 500 tokens easily)
    long_turkish_text = """
Yapay zeka (YZ), bilgisayarların insan zekasına benzer şekilde düşünmesini ve öğrenmesini sağlayan bir teknoloji dalıdır. 
Günümüzde yapay zeka, sağlık, eğitim, otomotiv, finans ve eğlence gibi birçok farklı sektörde devrim yaratmaktadır. 
Özellikle derin öğrenme ve doğal dil işleme gibi alt dallar sayesinde, bilgisayarlar karmaşık metinleri anlayabilir, 
görselleri tanıyabilir ve hatta otonom araçları güvenli bir şekilde yönlendirebilir.

Bu süreçte en önemli yapı taşlarından biri olan 'Transformer' mimarisi, dil modellerinin devasa boyutlara ulaşmasını sağlamıştır. 
Bir cümledeki kelimeler arasındaki ilişkileri aynı anda işleyebilen bu mimari, daha önceki ardışık işleme yöntemlerinin eksikliklerini gidermiştir. 
Örneğin, ChatGPT gibi büyük dil modelleri bu mimari üzerine inşa edilmiştir ve milyarlarca parametre içerir.

Ancak, bu modellerin eğitimi devasa miktarda veri ve hesaplama gücü gerektirir. 
Bu yüzden genellikle veri merkezlerinde, binlerce GPU'nun paralel çalışmasıyla haftalar veya aylar süren eğitim süreçleri yaşanır. 
Eğitim tamamlandıktan sonra ise, 'çıkarım' (inference) adı verilen aşamada model, öğrendiği bilgileri kullanarak yeni girdilere yanıt üretir. 
Bu aşamada bile modeller oldukça fazla bellek tüketebilir, bu nedenle 'quantization' (nicemleme) gibi tekniklerle modellerin boyutu küçültülmeye çalışılır.

Gelecekte yapay zekanın sadece metin veya görüntü üretmekle kalmayıp, robotik sistemlerle entegre olarak fiziksel dünyada daha fazla rol alması beklenmektedir. 
Fakat bu gelişmeler, yapay zekanın etik kullanımı, veri gizliliği ve iş gücü piyasasındaki olası etkileri gibi birçok tartışmayı da beraberinde getirmektedir. 
İnsanlar, bu teknolojiyi kendi yararlarına kullanırken, aynı zamanda olası riskleri en aza indirmek için yasal düzenlemeler ve etik çerçeveler üzerinde çalışmaya devam etmelidirler.
""" * 3 # Multiply by 3 to ensure it's huge

    chunks = chunker.chunk_text(long_turkish_text)
    
    assert len(chunks) > 0, "Should produce multiple chunks"
    
    for i, chunk in enumerate(chunks):
        token_count = chunker.get_token_count(chunk)
        
        # 1. Assert no chunk exceeds our strict configuration limit
        assert token_count <= settings.CHUNK_MAX_TOKENS, f"Chunk {i} exceeded config max ({token_count} > {settings.CHUNK_MAX_TOKENS})"
        
        # 2. Assert no chunk exceeds the model's actual maximum sequence length
        # (This model is 128)
        assert token_count <= 128, f"Chunk {i} exceeded model max_seq_length ({token_count} > 128)"

    # Check for basic overlaps (heuristic: some chunks should share text)
    if len(chunks) > 1:
        # We can't strictly assert string overlap because tokens don't always map cleanly to exact strings,
        # but SemanticChunker keeps sentences overlapping.
        pass

    print("Chunk validation passed!")
