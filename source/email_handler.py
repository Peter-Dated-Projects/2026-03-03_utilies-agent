"""
email_handler.py
----------------
Background worker that processes validated email jobs through the full pipeline:
  1. Scrape UARB portal (Playwright)
  2. Summarise with Qwen LLM
  3. Zip downloaded files
  4. Send result email
  5. Clean up temp directory
"""

import os
import uuid
import queue
import shutil
import threading
from source.logger import get_logger
from source.uarb_scraper import run_scrape_sync
from source.summariser import summarise_job
from source.zip_builder import create_zip
from source.email_sender import send_result_email

logger = get_logger(__name__)

email_queue: queue.Queue = queue.Queue()


def process_email_job(email_data: dict) -> None:
    """
    Execute the full pipeline for a single validated email job.

    Steps:
      1. Scrape the UARB portal for the matter ID and category
      2. Capture page text and download all relevant files
      3. Summarise file contents with the Qwen LLM
      4. Zip the downloaded files
      5. Send the result email with summary body + zip attachment
      6. Clean up the temporary download directory

    Args:
        email_data: Dict produced by email_filtering.process_and_filter_email().
                    Must contain: matter_id, category, sender.
    """
    matter_id   = email_data.get("matter_id", "UNKNOWN")
    category    = email_data.get("category", "UNKNOWN")
    sender      = email_data.get("sender", "")
    sender_name = email_data.get("sender_name", "User")

    logger.info("=== Processing job: Matter ID=%s | Category=%s ===", matter_id, category)

    # Create a unique temp directory for this job
    job_id = str(uuid.uuid4())
    download_dir = os.path.join("assets", job_id)

    zip_path: str | None = None

    try:
        # ── Step 1 & 2: Scrape UARB portal ───────────────────────────────────
        logger.info("[1/5] Scraping UARB portal...")
        scraper_result = run_scrape_sync(matter_id, category, download_dir)

        if not scraper_result.downloaded_files:
            logger.warning("No files downloaded for Matter ID: %s. Skipping LLM and zip steps.", matter_id)
        
        # ── Step 3: LLM summarisation ─────────────────────────────────────────
        logger.info("[2/5] Running LLM summarisation...")
        summary = summarise_job(
            matter_id=matter_id,
            category=category,
            page_text=scraper_result.page_text,
            files=scraper_result.downloaded_files,
            downloaded_count=len(scraper_result.downloaded_files),
            sender_name=sender_name,
        )

        # ── Step 4: Create zip ────────────────────────────────────────────────
        if scraper_result.downloaded_files:
            logger.info("[3/5] Creating zip archive...")
            try:
                zip_path, skipped_files = create_zip(download_dir, matter_id, category)
                if skipped_files:
                    summary += "\n\nNote: The following files were too large and were excluded from the ZIP attachment to meet email size limits:\n"
                    for sf in skipped_files:
                        summary += f"- {sf}\n"
            except Exception as e:
                logger.error("Failed to create zip: %s", e)
                zip_path = None
        else:
            logger.info("[3/5] No files to zip, skipping archive step.")

        # ── Step 5: Send result email ─────────────────────────────────────────
        if sender:
            logger.info("[4/5] Sending result email to %s...", sender)
            if zip_path:
                success = send_result_email(sender, matter_id, category, summary, zip_path)
            else:
                # No zip to attach — just send the summary text (which now handles the 0-file case cleanly).
                success = send_result_email(sender, matter_id, category, summary, None)

            if success:
                logger.info("[4/5] Email delivered successfully.")
            else:
                logger.error("[4/5] Failed to deliver result email.")
        else:
            logger.warning("[4/5] No sender address available, skipping email send.")

        logger.info("[5/5] Job complete for Matter ID: %s", matter_id)

    except Exception:
        logger.exception("Unexpected error processing job for Matter ID: %s", matter_id)

    finally:
        # ── Step 6: Cleanup ───────────────────────────────────────────────────
        if os.path.isdir(download_dir):
            shutil.rmtree(download_dir, ignore_errors=True)
            logger.debug("Cleaned up temp directory: %s", download_dir)
        if zip_path and os.path.isfile(zip_path):
            os.remove(zip_path)
            logger.debug("Cleaned up zip: %s", zip_path)


def worker() -> None:
    """
    Background daemon thread: continuously dequeues and processes email jobs.
    Blocks when the queue is empty.
    """
    logger.info("Email handler worker thread started, waiting for jobs...")
    while True:
        try:
            email_data = email_queue.get()
            process_email_job(email_data)
        except Exception as e:
            logger.error("Error in worker loop: %s", e)
        finally:
            email_queue.task_done()


def add_to_queue(email_data: dict) -> None:
    """
    Enqueue a validated email job for processing.

    Args:
        email_data: Dict with at least: matter_id, category, sender.
    """
    email_queue.put(email_data)
    logger.debug("Queued job for Matter ID: %s", email_data.get("matter_id"))


# Start the background worker as a daemon thread on module load
_worker_thread = threading.Thread(target=worker, daemon=True)
_worker_thread.start()
