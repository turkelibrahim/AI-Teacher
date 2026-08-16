import typing
from typing import Dict, Any
import docx
from docx.opc.exceptions import PackageNotFoundError
from app.core.config import settings

from .base import BaseDocumentExtractor, ExtractedDocument, ExtractedPage, validate_zip
from .errors import CorruptedDocumentError, LimitExceededError

class DOCXExtractor(BaseDocumentExtractor):
    def supports(self, mime_type: str, filename: str) -> bool:
        return mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or filename.lower().endswith(".docx")

    def extract(self, file_stream: typing.IO, metadata: Dict[str, Any] = None) -> ExtractedDocument:
        validate_zip(file_stream)
        try:
            doc = docx.Document(file_stream)
        except PackageNotFoundError as e:
            raise CorruptedDocumentError(f"Corrupted or invalid DOCX: {str(e)}")
        except Exception as e:
            raise CorruptedDocumentError(f"Failed to read DOCX: {str(e)}")

        paragraphs_text = []
        for element in doc.element.body:
            if element.tag.endswith('p'):
                for p in doc.paragraphs:
                    if p._element == element:
                        text = p.text.strip()
                        if text:
                            paragraphs_text.append(text)
                        break
            elif element.tag.endswith('tbl'):
                for t in doc.tables:
                    if t._element == element:
                        table_text = []
                        for row in t.rows:
                            row_data = [cell.text.strip() for cell in row.cells]
                            table_text.append(" | ".join(row_data))
                        paragraphs_text.append("\n".join(table_text))
                        break
        
        full_text = "\n\n".join(paragraphs_text).strip()
        
        if len(full_text) > settings.MAX_EXTRACTED_CHARACTERS:
            raise LimitExceededError("DOCX extracted text limit exceeded", "TEXT_LIMIT_EXCEEDED")
        
        page = ExtractedPage(
            page_number=1,
            text=full_text,
            metadata={}
        )
        
        return ExtractedDocument(
            pages=[page],
            title=doc.core_properties.title if hasattr(doc, 'core_properties') and doc.core_properties else None,
            ocr_required=False
        )
