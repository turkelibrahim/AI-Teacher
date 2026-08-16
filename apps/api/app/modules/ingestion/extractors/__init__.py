from .base import BaseDocumentExtractor, ExtractedDocument, ExtractedPage
from .pdf import PDFExtractor
from .docx import DOCXExtractor
from .pptx import PPTXExtractor
from .txt import TXTExtractor
from .markdown import MarkdownExtractor

def get_extractor(mime_type: str, filename: str) -> BaseDocumentExtractor:
    extractors = [
        PDFExtractor(),
        DOCXExtractor(),
        PPTXExtractor(),
        MarkdownExtractor(),
        TXTExtractor() # Fallback for text
    ]
    
    for extractor in extractors:
        if extractor.supports(mime_type, filename):
            return extractor
            
    raise ValueError("Unsupported document format")
