import typing
from typing import Dict, Any
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from app.core.config import settings

from .base import BaseDocumentExtractor, ExtractedDocument, ExtractedPage
from .errors import (
    CorruptedDocumentError, 
    EncryptedDocumentError, 
    LimitExceededError,
    OcrRequiredError
)

class PDFExtractor(BaseDocumentExtractor):
    def supports(self, mime_type: str, filename: str) -> bool:
        return mime_type == "application/pdf" or filename.lower().endswith(".pdf")

    def extract(self, file_stream: typing.IO, metadata: Dict[str, Any] = None) -> ExtractedDocument:
        try:
            reader = PdfReader(file_stream)
        except PyPdfError as e:
            raise CorruptedDocumentError(f"Corrupted or invalid PDF: {str(e)}")
            
        if reader.is_encrypted:
            raise EncryptedDocumentError("Encrypted PDFs are not supported")

        pages = []
        is_scanned = True
        total_text_length = 0
        
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                text = text.strip()
                if len(text) > 50:
                    is_scanned = False
                    
            if not text:
                text = ""
                
            total_text_length += len(text)
            
            if total_text_length > settings.MAX_EXTRACTED_CHARACTERS:
                raise LimitExceededError("Document exceeds maximum allowed character limit", "TEXT_LIMIT_EXCEEDED")
            
            # Use max single entry uncompressed bytes as page text limit
            if len(text) > settings.MAX_SINGLE_ENTRY_UNCOMPRESSED_BYTES:
                raise LimitExceededError("Page text limit exceeded", "TEXT_LIMIT_EXCEEDED")
                
            pages.append(ExtractedPage(
                page_number=i + 1,
                text=text,
                metadata={}
            ))
            
            if len(pages) > settings.MAX_INGESTION_PAGES:
                raise LimitExceededError("PDF exceeds maximum allowed pages limit", "PAGE_LIMIT_EXCEEDED")
                
        ocr_required = len(pages) > 0 and total_text_length < (len(pages) * 20)
        
        if ocr_required:
            raise OcrRequiredError("Document requires OCR")
        
        doc_info = reader.metadata
        title = doc_info.title if doc_info and doc_info.title else None
        
        return ExtractedDocument(
            pages=pages,
            title=title,
            ocr_required=ocr_required
        )
