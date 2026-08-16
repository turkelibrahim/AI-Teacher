import typing
from typing import Dict, Any
import pptx
from pptx.exc import PackageNotFoundError
from app.core.config import settings

from .base import BaseDocumentExtractor, ExtractedDocument, ExtractedPage, validate_zip
from .errors import CorruptedDocumentError, LimitExceededError

class PPTXExtractor(BaseDocumentExtractor):
    def supports(self, mime_type: str, filename: str) -> bool:
        return mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation" or filename.lower().endswith(".pptx")

    def extract(self, file_stream: typing.IO, metadata: Dict[str, Any] = None) -> ExtractedDocument:
        validate_zip(file_stream)
        try:
            prs = pptx.Presentation(file_stream)
        except PackageNotFoundError as e:
            raise CorruptedDocumentError(f"Corrupted or invalid PPTX: {str(e)}")
        except Exception as e:
            raise CorruptedDocumentError(f"Corrupted or invalid PPTX: {str(e)}")

        pages = []
        total_text_length = 0
        for i, slide in enumerate(prs.slides):
            slide_text = []
            
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
                if notes_text:
                    slide_text.append(f"[Notes: {notes_text}]")
                    
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    text = shape.text.strip()
                    if text:
                        slide_text.append(text)
                elif shape.has_table:
                    table_text = []
                    for row in shape.table.rows:
                        row_data = [cell.text_frame.text.replace("\n", " ").strip() for cell in row.cells]
                        table_text.append(" | ".join(row_data))
                    slide_text.append("\n".join(table_text))
                    
            full_text = "\n\n".join(slide_text).strip()
            total_text_length += len(full_text)
            
            if total_text_length > settings.MAX_EXTRACTED_CHARACTERS:
                raise LimitExceededError("Document exceeds maximum allowed character limit", "TEXT_LIMIT_EXCEEDED")
            
            if len(full_text) > settings.MAX_SINGLE_ENTRY_UNCOMPRESSED_BYTES:
                raise LimitExceededError(f"Slide {i+1} text limit exceeded", "TEXT_LIMIT_EXCEEDED")
                
            pages.append(ExtractedPage(
                page_number=i + 1,
                text=full_text,
                metadata={}
            ))
            
            if len(pages) > settings.MAX_INGESTION_PAGES:
                raise LimitExceededError("PPTX exceeds maximum allowed slides limit", "PAGE_LIMIT_EXCEEDED")
        
        doc_title = prs.core_properties.title if hasattr(prs, 'core_properties') and prs.core_properties else None
        
        return ExtractedDocument(
            pages=pages,
            title=doc_title,
            ocr_required=False
        )
