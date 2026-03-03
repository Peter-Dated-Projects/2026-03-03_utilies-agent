"""
summariser.py
-------------
Orchestrates the LLM summarisation step:
  - Extracts text from PDF files
  - Skips media files (recordings) gracefully
  - Builds a structured prompt
  - Calls the Qwen API and returns the summary string
"""

import os
from source.logger import get_logger
from source import qwen_client
from source.pdf_extractor import extract_text_from_pdf

logger = get_logger(__name__)

# Extensions for which we can extract text
PDF_EXTENSIONS = {".pdf"}

# Extensions we skip sending to the LLM
MEDIA_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".mov", ".avi"}

SYSTEM_PROMPT = """
You are an automated regulatory data extractor. Your job is to extract metadata from the provided raw scraped text and format it into a specific email response.

You MUST output EXACTLY one of these two templates, filling in the bracketed information based on the raw text:

TEMPLATE A (If Downloaded Count is greater than 0):
"Hi [Sender Name], [Matter ID] is about the [Title]. It relates to [Type/Status] within the [Category] category. The matter had an initial filing on [Initial Date] and a final filing on [Final Date]. I found [X] Exhibits, [Y] Key Documents, [Z] Other Documents, and [W] Transcripts and Recordings. I downloaded [Downloaded Count] out of the [Total Count] [Requested Document Type] and am attaching them as a ZIP here."

TEMPLATE B (If Downloaded Count is 0):
"Hi [Sender Name], [Matter ID] is about the [Title]. It relates to [Type/Status] within the [Category] category. The matter had an initial filing on [Initial Date] and a final filing on [Final Date]. I found [X] Exhibits, [Y] Key Documents, [Z] Other Documents, and [W] Transcripts and Recordings. I was unable to download any [Requested Document Type] from that matter, so no ZIP file is attached."

Rules:
1. Do not add any conversational filler before or after the template.
2. Format dates into readable English (e.g., April 7, 2025 instead of 04/07/2025).
3. If a document count is 0, write "no" instead of "0" (e.g., "no Transcripts").
4. Combine 0 counts naturally (e.g., "no Transcripts or Recordings").
5. Output plain text only. No markdown, asterisks, or bolding.
"""

_MAX_TEXT_CHARS = 1_000  # Truncate individual file text to stay within context limits


def _build_user_message(
    matter_id: str,
    category: str,
    page_text: str,
    file_entries: list[dict],
    downloaded_count: int = 0,
    sender_name: str = "User",
) -> str:
    """Build the full user-facing prompt string."""
    lines: list[str] = []

    lines.append(f"Matter ID: {matter_id} | Category: {category}")
    lines.append(f"Downloaded Count: {downloaded_count}")
    lines.append(f"Sender Name: {sender_name}")
    lines.append("")

    if page_text.strip():
        lines.append("--- UARB PORTAL PAGE CONTENT ---")
        # Truncate very long page text
        trimmed = page_text.strip()[:8_000]
        lines.append(trimmed)
        if len(page_text.strip()) > 8_000:
            lines.append("[... content truncated ...]")
        lines.append("")

    lines.append("--- DOCUMENTS ---")
    for entry in file_entries:
        lines.append(f"\n[File: {entry['filename']}]")
        if entry.get("skipped"):
            lines.append(f"(Media file – content not available for analysis)")
        elif entry.get("text"):
            text = entry["text"]
            if len(text) > _MAX_TEXT_CHARS:
                text = text[:_MAX_TEXT_CHARS] + "\n[... content truncated ...]"
            lines.append(text)
        else:
            lines.append("(No text could be extracted from this file)")

    lines.append("")
    lines.append(
        "Please provide a clear, concise, and succinct summary covering:\n"
        "1. Overall context of this matter based on the portal page content\n"
        "2. Key metadata for each document (type, date, parties if visible)\n"
        "3. Key points and findings from the document contents\n"
        "4. Any important observations specific to this matter"
    )

    return "\n".join(lines)


def summarise_job(
    matter_id: str,
    category: str,
    page_text: str,
    files: list[str],
    downloaded_count: int | None = None,
    sender_name: str = "User",
) -> str:
    """
    Build a prompt from all downloaded files and page text, then call Qwen.

    Args:
        matter_id:  e.g. "M12205"
        category:   e.g. "Exhibits"
        page_text:  Raw text scraped from the UARB portal results page.
        files:      List of absolute paths to downloaded files.

    Returns:
        The LLM's summary as a plain string.
    """
    file_entries: list[dict] = []

    for file_path in files:
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()

        if ext in MEDIA_EXTENSIONS:
            logger.info("Skipping media file for LLM: %s", filename)
            file_entries.append({"filename": filename, "skipped": True, "text": ""})

        elif ext in PDF_EXTENSIONS:
            logger.info("Extracting text from PDF: %s", filename)
            text = extract_text_from_pdf(file_path)
            file_entries.append({"filename": filename, "skipped": False, "text": text})

        else:
            # For any other file type (docx, txt, etc.), attempt a plain read
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                file_entries.append({"filename": filename, "skipped": False, "text": text})
            except Exception as e:
                logger.warning("Could not read file '%s': %s", filename, e)
                file_entries.append({"filename": filename, "skipped": False, "text": ""})

    if not file_entries and not page_text.strip():
        logger.warning("No content available for LLM summarisation (Matter ID: %s).", matter_id)
        return (
            f"No files or page content were available for Matter ID {matter_id} "
            f"under the category '{category}'."
        )

    n_downloaded = downloaded_count if downloaded_count is not None else len(file_entries)
    user_message = _build_user_message(matter_id, category, page_text, file_entries, n_downloaded, sender_name)

    logger.info(
        "Sending %d file(s) to Qwen for Matter ID: %s (prompt length: %d chars)",
        len(file_entries), matter_id, len(user_message)
    )

    print("\n" + "=" * 60)
    print("  QWEN PROMPT (user message)")
    print("=" * 60)
    print(user_message)
    print("=" * 60 + "\n")

    try:
        summary = qwen_client.chat(SYSTEM_PROMPT, user_message)
        logger.info("Received summary from Qwen (%d chars).", len(summary))
        return summary
    except Exception as e:
        logger.error("Qwen API call failed: %s", e)
        return (
            f"Summary generation failed for Matter ID {matter_id} ({category}).\n"
            f"Error: {e}\n\n"
            f"Downloaded files have been attached as a zip."
        )
