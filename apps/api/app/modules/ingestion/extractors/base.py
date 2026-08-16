from typing import Dict, Any, List
from io import BytesIO

class ExtractedPage:
    def __init__(self, page_number: int, text: str, metadata: Dict[str, Any] = None, page_label: str = None):
        self.page_number = page_number
        self.text = text
        self.metadata = metadata or {}
        self.page_label = page_label
        self.character_count = len(text)

class ExtractedDocument:
    def __init__(self, pages: List[ExtractedPage], title: str = None, language: str = None, ocr_required: bool = False):
        self.pages = pages
        self.title = title
        self.language = language
        self.ocr_required = ocr_required
        self.total_pages = len(pages)
        self.total_characters = sum(page.character_count for page in pages)
        self.plain_text = "\n\n".join(page.text for page in pages) if pages else ""

class BaseDocumentExtractor:
    def supports(self, mime_type: str, filename: str) -> bool:
        raise NotImplementedError

    def extract(self, file_stream: BytesIO, metadata: Dict[str, Any] = None) -> ExtractedDocument:
        raise NotImplementedError

import zipfile
from app.core.config import settings
from .errors import ZipBombError

def validate_zip(file_stream):
    try:
        with zipfile.ZipFile(file_stream, 'r') as zf:
            infolist = zf.infolist()
            if len(infolist) > settings.MAX_OFFICE_ENTRIES:
                raise ZipBombError("ZIP archive contains too many entries")
            
            total_size = 0
            for info in infolist:
                if info.file_size > settings.MAX_SINGLE_ENTRY_UNCOMPRESSED_BYTES:
                    raise ZipBombError("ZIP archive contains an entry exceeding size limits")
                total_size += info.file_size
                
            if total_size > settings.MAX_OFFICE_UNCOMPRESSED_BYTES:
                raise ZipBombError("ZIP archive uncompressed size exceeds limits")
    except zipfile.BadZipFile:
        # Not a zip file, or corrupted. We let the actual extractor handle corruption errors.
        pass
    finally:
        file_stream.seek(0)

