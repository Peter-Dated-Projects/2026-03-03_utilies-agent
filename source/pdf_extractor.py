"""
pdf_extractor.py
----------------
Extracts plain text from PDF files.
Uses pdfplumber as the primary method with a pypdf fallback.
"""

from source.logger import get_logger

logger = get_logger(__name__)


MAX_PDF_PAGES = 3  # Only parse the first N pages of each PDF


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from the first MAX_PDF_PAGES pages of a PDF file.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        Extracted text as a single string, or an empty string on failure.
    """
    # --- Primary: pdfplumber ---
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            pages_text = []
            for page in pdf.pages[:MAX_PDF_PAGES]:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            if pages_text:
                result = "\n\n".join(pages_text)
                logger.debug("pdfplumber extracted %d chars from '%s'.", len(result), file_path)
                return result
    except ImportError:
        logger.warning("pdfplumber not installed, falling back to pypdf.")
    except Exception as e:
        logger.warning("pdfplumber failed on '%s': %s. Trying pypdf.", file_path, e)

    # --- Fallback: pypdf ---
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        pages_text = []
        for page in reader.pages[:MAX_PDF_PAGES]:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        result = "\n\n".join(pages_text)
        logger.debug("pypdf extracted %d chars from '%s'.", len(result), file_path)
        return result
    except ImportError:
        logger.error("Neither pdfplumber nor pypdf is installed. Cannot extract PDF text.")
    except Exception as e:
        logger.error("pypdf also failed on '%s': %s", file_path, e)

    return ""
