import typing
from typing import Dict, Any
from app.core.config import settings

from .base import BaseDocumentExtractor, ExtractedDocument, ExtractedPage
from .errors import CorruptedDocumentError, LimitExceededError

class MarkdownExtractor(BaseDocumentExtractor):
    def supports(self, mime_type: str, filename: str) -> bool:
        return mime_type == "text/markdown" or filename.lower().endswith((".md", ".markdown"))

    def extract(self, file_stream: typing.IO, metadata: Dict[str, Any] = None) -> ExtractedDocument:
        raw_bytes = file_stream.read()
        
        if len(raw_bytes) > settings.MAX_SINGLE_ENTRY_UNCOMPRESSED_BYTES:
            raise LimitExceededError("Markdown file limit exceeded", "TEXT_LIMIT_EXCEEDED")
            
        try:
            text = raw_bytes.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                text = raw_bytes.decode('utf-8')
            except UnicodeDecodeError:
                raise CorruptedDocumentError("Could not decode Markdown file. Ensure it is UTF-8 encoded.")
                
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
        
        page = ExtractedPage(
            page_number=1,
            text=text.strip(),
            metadata={}
        )
        
        return ExtractedDocument(
            pages=[page],
            title=None,
            ocr_required=False
        )
