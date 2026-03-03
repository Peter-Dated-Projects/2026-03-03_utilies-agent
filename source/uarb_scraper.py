"""
uarb_scraper.py
---------------
Playwright-based scraper for the UARB FileMaker WebDirect portal.
Promoted from scripts/test_uarb_search.py into a reusable async function.
"""

import os
import uuid
import asyncio
from dataclasses import dataclass, field
from playwright.async_api import async_playwright, Page
from source.logger import get_logger

logger = get_logger(__name__)

PORTAL_URL = "https://uarb.novascotia.ca/fmi/webd/UARB15"

# FileMaker element IDs for each document category tab
TAB_SELECTORS: dict[str, str] = {
    "Exhibits":        "#b0p0o277i0i0r1",
    "Key Documents":   "#b0p0o278i0i0r1",
    "Other Documents": "#b0p0o279i0i0r1",
    "Transcripts":     "#b0p0o280i0i0r1",
    "Recordings":      "#b0p0o281i0i0r1",
}

# File extensions that should NOT be sent to the LLM
MEDIA_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".mov", ".avi"}


@dataclass
class ScraperResult:
    downloaded_files: list[str] = field(default_factory=list)
    """Absolute paths to all files that were downloaded."""

    page_text: str = ""
    """Raw visible text scraped from the results page for this category."""

    is_recording: bool = False
    """True when the category is 'Recordings' (media files, skip LLM content analysis)."""


async def _download_from_modal(page: Page, download_dir: str) -> str | None:
    """
    Handles the FileMaker download modal:
      - Waits for modal to appear
      - Clicks the download button
      - Saves the file to download_dir
      - Closes the modal

    Returns the saved file path, or None if anything failed.
    """
    try:
        modal = page.locator(".fm-modal-dialog")
        await modal.wait_for(state="visible", timeout=5000)

        async with page.expect_download() as download_info:
            await page.click(".fm-download-button")

        download = await download_info.value
        file_path = os.path.join(download_dir, download.suggested_filename)
        await download.save_as(file_path)
        logger.info("Downloaded: %s", file_path)

        # Close the modal
        await page.click(".v-slot-primary .v-button-primary")
        await page.locator(".v-window-modalitycurtain").wait_for(state="hidden")

        return file_path
    except Exception as e:
        logger.warning("Error downloading from modal: %s", e)
        # Attempt to close any lingering modal so subsequent clicks still work
        try:
            close_btn = page.locator(".v-slot-primary .v-button-primary")
            if await close_btn.is_visible():
                await close_btn.click()
            await page.locator(".v-window-modalitycurtain").wait_for(state="hidden", timeout=2000)
        except Exception:
            pass
        return None


async def scrape_uarb(matter_id: str, category: str, download_dir: str) -> ScraperResult:
    """
    Navigate to the UARB portal, enter the matter ID, switch to the correct
    category tab, capture the raw page text, and download all available files.

    Args:
        matter_id:    Standardised matter ID, e.g. "M12205".
        category:     One of the five document categories.
        download_dir: Directory where downloaded files will be saved.
                      Will be created if it does not exist.

    Returns:
        A ScraperResult dataclass.
    """
    os.makedirs(download_dir, exist_ok=True)
    result = ScraperResult(is_recording=(category == "Recordings"))

    target_tab_id = TAB_SELECTORS.get(category)
    if not target_tab_id:
        logger.error("Unknown category '%s'. No tab selector available.", category)
        return result

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()

            logger.info("Navigating to UARB portal for Matter ID: %s, Category: %s", matter_id, category)
            await page.goto(PORTAL_URL)

            # Wait for the search input to be ready
            search_input_selector = "#b0p0o254i0i0r1"
            await page.wait_for_selector(search_input_selector)

            # Enter the matter ID
            await page.locator(search_input_selector).click()
            await page.wait_for_timeout(500)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(matter_id, delay=50)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            await page.wait_for_load_state("networkidle")

            # Switch to the requested category tab
            logger.info("Switching to tab: %s (%s)", category, target_tab_id)
            await page.wait_for_selector(target_tab_id)
            await page.click(target_tab_id)

            # Wait for GO GET IT buttons to appear (or timeout gracefully)
            try:
                await page.locator('text="GO GET IT"').first.wait_for(state="visible", timeout=5000)
            except Exception:
                logger.warning("No 'GO GET IT' buttons appeared for %s / %s.", matter_id, category)

            # Extra wait for JS event handlers to bind
            await page.wait_for_timeout(3000)

            # ── Capture raw page text BEFORE downloading ──────────────────────
            try:
                result.page_text = await page.inner_text("body")
                logger.debug("Captured %d chars of page text.", len(result.page_text))
            except Exception as e:
                logger.warning("Could not capture page text: %s", e)

            # ── Download files ────────────────────────────────────────────────
            download_elements = await page.locator('text="GO GET IT"').all()
            logger.info("Found %d 'GO GET IT' buttons.", len(download_elements))

            for i, element in enumerate(download_elements):
                logger.info("[%d/%d] Clicking 'GO GET IT'...", i + 1, len(download_elements))
                await element.click(delay=100)
                file_path = await _download_from_modal(page, download_dir)
                if file_path:
                    result.downloaded_files.append(file_path)

                # Dismiss any residual overlay
                try:
                    close_btn = page.locator(".v-slot-primary .v-button-primary")
                    if await close_btn.is_visible():
                        await close_btn.click()
                    await page.locator(".v-window-modalitycurtain").wait_for(state="hidden", timeout=2000)
                except Exception:
                    pass

                # Scroll the next button into view inside FileMaker's scroll container
                if i + 1 < len(download_elements):
                    await download_elements[i + 1].evaluate("""node => {
                        let parent = node.parentElement;
                        while (parent) {
                            const style = window.getComputedStyle(parent);
                            const overflow = style.overflow + style.overflowY;
                            if (overflow.includes('auto') || overflow.includes('scroll')) {
                                const rect = node.getBoundingClientRect();
                                const parentRect = parent.getBoundingClientRect();
                                const offset = rect.top - parentRect.top - (parentRect.height / 2) + (rect.height / 2);
                                parent.scrollBy({ top: offset, behavior: 'smooth' });
                                return;
                            }
                            parent = parent.parentElement;
                        }
                        node.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }""")
                    await page.wait_for_timeout(600)

            await browser.close()

    except Exception as e:
        logger.exception("Unexpected error during UARB scrape for Matter ID: %s", matter_id)

    logger.info(
        "Scrape complete. %d file(s) downloaded for Matter ID: %s / %s",
        len(result.downloaded_files), matter_id, category
    )
    return result


def run_scrape_sync(matter_id: str, category: str, download_dir: str) -> ScraperResult:
    """
    Synchronous entry-point — runs the async scraper in a new event loop.
    Useful when calling from a non-async context (e.g. the worker thread).
    """
    return asyncio.run(scrape_uarb(matter_id, category, download_dir))
