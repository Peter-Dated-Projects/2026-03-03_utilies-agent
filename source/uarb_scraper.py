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
        await page.locator(".v-window-modalitycurtain").wait_for(state="hidden", timeout=5000)

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


async def scrape_uarb(matter_id: str, category: str, download_dir: str, max_downloads: int = 10) -> ScraperResult:
    """
    Navigate to the UARB portal, enter the matter ID, switch to the correct
    category tab, capture the raw page text, and download up to max_downloads files.

    Uses a scroll-and-scan loop with JS-dispatched mouse events and JS scrollTop
    mutation to handle Vaadin's virtualised row rendering in headless mode.

    Args:
        matter_id:     Standardised matter ID, e.g. "M12205".
        category:      One of the five document categories.
        download_dir:  Directory where downloaded files will be saved.
                       Will be created if it does not exist.
        max_downloads: Maximum number of files to download (default: 10).

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
            context = await browser.new_context(
                accept_downloads=True,
                # FileMaker WebDirect needs a large viewport to render correctly in headless mode
                viewport={"width": 1440, "height": 900},
            )
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

            await page.wait_for_timeout(3000)
            logger.info("Tab '%s' active. Starting scroll-and-scan loop...", category)

            # ── Capture raw page text BEFORE downloading ──────────────────────
            try:
                result.page_text = await page.inner_text("body")
                logger.debug("Captured %d chars of page text.", len(result.page_text))
            except Exception as e:
                logger.warning("Could not capture page text: %s", e)

            # ── Scroll-and-scan download loop ─────────────────────────────────
            downloaded_count = 0
            processed_ids: set[str] = set()
            consecutive_empty_scrolls = 0
            MAX_EMPTY_SCROLLS = 5
            SCROLL_STEP = 204  # 3 rows × 68 px each
            current_scroll_top = 0

            while downloaded_count < max_downloads:
                # Guard: dismiss any lingering modal curtain before scanning
                try:
                    curtain = page.locator(".v-window-modalitycurtain")
                    if await curtain.is_visible():
                        close_btn = page.locator(".v-slot-primary .v-button-primary")
                        if await close_btn.is_visible():
                            await close_btn.click()
                        await curtain.wait_for(state="hidden", timeout=3000)
                except Exception:
                    pass

                # Scan: find all currently rendered "GO GET IT" buttons
                buttons = await page.get_by_role("button", name="GO GET IT").all()

                new_buttons_found = False
                for btn in buttons:
                    if downloaded_count >= max_downloads:
                        break

                    btn_id = await btn.get_attribute("id")
                    if btn_id is None or btn_id in processed_ids:
                        continue

                    processed_ids.add(btn_id)
                    new_buttons_found = True
                    consecutive_empty_scrolls = 0

                    logger.info("[%d/%d] Clicking 'GO GET IT' (id=%s)...", downloaded_count + 1, max_downloads, btn_id)

                    # Dispatch mousedown→mouseup→click via JS.
                    # Required in headless mode: Vaadin listens on mousedown, and elements
                    # outside the viewport cannot receive Playwright's normal .click().
                    await page.evaluate("""
                        (id) => {
                            const el = document.getElementById(id);
                            if (!el) return;
                            ['mousedown', 'mouseup', 'click'].forEach(type => {
                                el.dispatchEvent(new MouseEvent(type, {
                                    bubbles: true, cancelable: true,
                                    view: window, buttons: 1
                                }));
                            });
                        }
                    """, btn_id)

                    file_path = await _download_from_modal(page, download_dir)

                    # Defensive dismissal in case modal close didn't fully complete
                    try:
                        close_btn = page.locator(".v-slot-primary .v-button-primary")
                        if await close_btn.is_visible():
                            await close_btn.click()
                        await page.locator(".v-window-modalitycurtain").wait_for(state="hidden", timeout=3000)
                    except Exception:
                        pass

                    if file_path:
                        result.downloaded_files.append(file_path)
                        downloaded_count += 1

                if downloaded_count >= max_downloads:
                    logger.info("Reached download cap of %d. Stopping.", max_downloads)
                    break

                if not new_buttons_found:
                    consecutive_empty_scrolls += 1
                    if consecutive_empty_scrolls >= MAX_EMPTY_SCROLLS:
                        logger.info(
                            "No new rows after %d consecutive scrolls. End of list.", MAX_EMPTY_SCROLLS
                        )
                        break

                    logger.debug(
                        "No new buttons (miss #%d). Advancing virtual scroll by %d px...",
                        consecutive_empty_scrolls, SCROLL_STEP,
                    )
                    # Directly mutate scrollTop on Vaadin's internal scroller and fire a
                    # scroll event so its virtual row engine fetches the next batch of rows.
                    current_scroll_top += SCROLL_STEP
                    await page.evaluate("""
                        (scrollTop) => {
                            const scroller = document.querySelector('.v-grid-scroller-vertical');
                            if (scroller) {
                                scroller.scrollTop = scrollTop;
                                scroller.dispatchEvent(new Event('scroll', { bubbles: true }));
                            }
                        }
                    """, current_scroll_top)
                    await page.wait_for_timeout(1500)

            await browser.close()

    except Exception as e:
        logger.exception("Unexpected error during UARB scrape for Matter ID: %s", matter_id)

    logger.info(
        "Scrape complete. %d file(s) downloaded for Matter ID: %s / %s",
        len(result.downloaded_files), matter_id, category
    )
    return result


def run_scrape_sync(matter_id: str, category: str, download_dir: str, max_downloads: int = 10) -> ScraperResult:
    """
    Synchronous entry-point — runs the async scraper in a new event loop.
    Useful when calling from a non-async context (e.g. the worker thread).
    """
    return asyncio.run(scrape_uarb(matter_id, category, download_dir, max_downloads))
