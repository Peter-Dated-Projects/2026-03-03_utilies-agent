"""
test_full_pipeline.py
---------------------
End-to-end integration test for the full email pipeline.

Simulates an inbound email request, runs the real pipeline
(UARB scrape + Qwen LLM), and prints the result as a mock
outbound email instead of actually sending it.

Usage:
    uv run python scripts/test_full_pipeline.py
"""

import os
import sys
import uuid
import shutil
from dotenv import load_dotenv

# Make sure source/ is importable from the project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

from source.uarb_scraper import run_scrape_sync
from source.summariser import summarise_job
from source.zip_builder import create_zip
from source.logger import get_logger

logger = get_logger("test_full_pipeline")

# ── Mock email request ────────────────────────────────────────────────────────
MOCK_EMAIL = {
    "sender":    "test.requester@example.com",
    "subject":   "M12205 Exhibits request",
    "body":      "Hi, please send me the Exhibits for M12205. Thanks!",
    "matter_id": "M12205",
    "category":  "Exhibits",
}
# ─────────────────────────────────────────────────────────────────────────────


def print_mock_email(to: str, subject: str, body: str, zip_path: str | None) -> None:
    """Pretty-print the outbound result email to stdout."""
    from_addr = os.environ.get("EMAIL", "agent@example.com")
    app_name  = os.environ.get("APP_NAME", "")
    from_display = f"{app_name} <{from_addr}>" if app_name else from_addr

    print("\n" + "=" * 60)
    print("  MOCK OUTBOUND EMAIL")
    print("=" * 60)
    print(f"  From:    {from_display}")
    print(f"  To:      {to}")
    print(f"  Subject: {subject}")
    if zip_path:
        zip_size = os.path.getsize(zip_path) // 1024
        print(f"  Attach:  {os.path.basename(zip_path)} ({zip_size} KB)")
    else:
        print("  Attach:  (none)")
    print("-" * 60)
    print(body)
    print("=" * 60 + "\n")


def main() -> None:
    matter_id = MOCK_EMAIL["matter_id"]
    category  = MOCK_EMAIL["category"]
    sender    = MOCK_EMAIL["sender"]

    print(f"\n>>> Mock email received from: {sender}")
    print(f"    Subject : {MOCK_EMAIL['subject']}")
    print(f"    Matter  : {matter_id} | Category: {category}\n")

    # Temp directory for this test run
    job_id = str(uuid.uuid4())
    download_dir = os.path.join("assets", job_id)
    zip_path = None

    try:
        # Step 1: Scrape UARB
        print(f"[1/3] Scraping UARB portal for {matter_id} / {category}...")
        result = run_scrape_sync(matter_id, category, download_dir)
        print(f"      Downloaded {len(result.downloaded_files)} file(s).")

        # Step 2: LLM summary
        print("[2/3] Generating LLM summary via Qwen...")
        summary = summarise_job(
            matter_id=matter_id,
            category=category,
            page_text=result.page_text,
            files=result.downloaded_files,
        )
        print(f"      Summary: {len(summary)} chars received.")

        # Step 3: Zip
        if result.downloaded_files:
            print("[3/3] Zipping files...")
            zip_path = create_zip(download_dir, matter_id, category)
            print(f"      Archive: {zip_path}")
        else:
            print("[3/3] No files downloaded — skipping zip.")
            # Write a placeholder file so the zip step doesn't fail
            os.makedirs(download_dir, exist_ok=True)
            note = os.path.join(download_dir, "no_files.txt")
            with open(note, "w") as f:
                f.write(f"No files found for {matter_id} / {category}.\n")
            zip_path = create_zip(download_dir, matter_id, category)

        # Output mock email
        subject = f"[UARB Agent] Matter {matter_id} – {category} Summary"
        print_mock_email(sender, subject, summary, zip_path)

    finally:
        # Clean up temp directory and zip
        if os.path.isdir(download_dir):
            shutil.rmtree(download_dir, ignore_errors=True)
        if zip_path and os.path.isfile(zip_path):
            os.remove(zip_path)
        print(">>> Temp files cleaned up. Test complete.\n")


if __name__ == "__main__":
    main()
