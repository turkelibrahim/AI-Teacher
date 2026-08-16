import pytest
from app.modules.ingestion.extractors.pdf import PDFExtractor
from app.modules.ingestion.extractors.docx import DOCXExtractor
from app.modules.ingestion.extractors.pptx import PPTXExtractor
from app.modules.ingestion.extractors.txt import TXTExtractor
from app.modules.ingestion.extractors.markdown import MarkdownExtractor
from app.modules.ingestion.extractors.errors import LimitExceededError, CorruptedDocumentError, OcrRequiredError, ZipBombError, EncryptedDocumentError
import io
import zipfile

def test_txt_extraction():
    extractor = TXTExtractor()
    content = b"Hello, World!\r\nThis is a test."
    stream = io.BytesIO(content)
    doc = extractor.extract(stream)
    assert doc.total_pages == 1
    assert "Hello, World!\nThis is a test." in doc.plain_text

def test_markdown_extraction():
    extractor = MarkdownExtractor()
    content = b"# Heading\n\n- List item\n- List item 2"
    stream = io.BytesIO(content)
    doc = extractor.extract(stream)
    assert doc.total_pages == 1
    assert "# Heading" in doc.plain_text

def test_normalization():
    extractor = TXTExtractor()
    content = b"Line 1\x00\r\nLine 2\rLine 3"
    stream = io.BytesIO(content)
    doc = extractor.extract(stream)
    assert doc.plain_text == "Line 1\nLine 2\nLine 3"

def test_pdf_extraction():
    extractor = PDFExtractor()
    with open('tests/fixtures/test.pdf', 'rb') as f:
        doc = extractor.extract(f)
    assert doc.total_pages == 2
    assert "Valid Text PDF" in doc.plain_text
    assert "This is page 1." in doc.plain_text

def test_pdf_ocr_required():
    extractor = PDFExtractor()
    with open('tests/fixtures/scanned.pdf', 'rb') as f:
        with pytest.raises(OcrRequiredError):
            extractor.extract(f)

def test_pdf_encrypted():
    extractor = PDFExtractor()
    with open('tests/fixtures/encrypted.pdf', 'rb') as f:
        with pytest.raises(EncryptedDocumentError):
            extractor.extract(f)

def test_docx_extraction():
    extractor = DOCXExtractor()
    with open('tests/fixtures/test.docx', 'rb') as f:
        doc = extractor.extract(f)
    assert doc.total_pages == 1
    assert "Test Document" in doc.plain_text
    assert "This is paragraph 1." in doc.plain_text
    assert "A1 | B1" in doc.plain_text

def test_pptx_extraction():
    extractor = PPTXExtractor()
    with open('tests/fixtures/test.pptx', 'rb') as f:
        doc = extractor.extract(f)
    assert doc.total_pages == 2
    assert "Slide 1" in doc.plain_text
    assert "Body 1" in doc.plain_text

def test_zip_bomb_protection():
    extractor = DOCXExtractor()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as zf:
        for i in range(10001):
            zf.writestr(f"file_{i}.xml", b"A" * 10)
    stream.seek(0)
    with pytest.raises(ZipBombError):
        extractor.extract(stream)

def test_extraction_limits():
    extractor = TXTExtractor()
    content = b"A" * (10 * 1024 * 1024 + 1)
    stream = io.BytesIO(content)
    with pytest.raises(LimitExceededError):
        extractor.extract(stream)
