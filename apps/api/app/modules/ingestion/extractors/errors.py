class ExtractionError(Exception):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code

class UnsupportedFormatError(ExtractionError):
    def __init__(self, message: str = "Unsupported document format"):
        super().__init__(message, "UNSUPPORTED_FORMAT")

class CorruptedDocumentError(ExtractionError):
    def __init__(self, message: str = "Document is corrupted or unreadable"):
        super().__init__(message, "CORRUPTED_DOCUMENT")

class EncryptedDocumentError(ExtractionError):
    def __init__(self, message: str = "Document is encrypted"):
        super().__init__(message, "ENCRYPTED_PDF")

class OcrRequiredError(ExtractionError):
    def __init__(self, message: str = "Document requires OCR"):
        super().__init__(message, "OCR_REQUIRED")

class LimitExceededError(ExtractionError):
    def __init__(self, message: str, code: str = "PAGE_LIMIT_EXCEEDED"):
        super().__init__(message, code)

class ZipBombError(ExtractionError):
    def __init__(self, message: str = "Suspicious ZIP archive detected"):
        super().__init__(message, "ZIP_LIMIT_EXCEEDED")
