import re
import os
import uuid
import asyncio
from playwright.async_api import async_playwright


def extract_matter_id(text):
    """
    Checks a string for a Matter ID.
    Supports formats: M12345 or M-12345.
    Returns the ID in uppercase without the hyphen.
    """
    pattern = r'\bM-?\d{5}\b'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(0).replace('-', '').upper()
    return None


async def download_from_modal(page, download_dir):
    try:
        # Wait for modal to be visible. FileMaker does a server round-trip before showing it,
        # so give it a generous timeout.
        modal = page.locator('.fm-modal-dialog')
        await modal.wait_for(state="visible", timeout=5000)

        # Trigger download and save using the suggested filename.
        async with page.expect_download() as download_info:
            # In headless mode page.click() still works for the download button since it's
            # inside the modal (which is fully in-viewport) and has no glass pane overlay.
            await page.click('.fm-download-button')

        download = await download_info.value
        file_path = os.path.join(download_dir, download.suggested_filename)
        await download.save_as(file_path)
        print(f"Downloaded: {file_path}")

        # Close the modal via the primary Close button.
        await page.click(".v-slot-primary .v-button-primary")

        # Wait for the modality curtain to fully disappear before continuing.
        await page.locator(".v-window-modalitycurtain").wait_for(state="hidden", timeout=5000)

        return file_path
    except Exception as e:
        print(f"Error downloading from modal: {e}")
        return None


async def run_uarb_search(matter_id, doc_type, max_downloads=10):
    job_id = str(uuid.uuid4())
    download_dir = os.path.join("assets", job_id)
    os.makedirs(download_dir, exist_ok=True)
    print(f"Job Initialized. Temporary directory: {download_dir}")

    tab_selectors = {
        "Exhibits": "#b0p0o277i0i0r1",
        "Key Documents": "#b0p0o278i0i0r1",
        "Other Documents": "#b0p0o279i0i0r1",
        "Transcripts": "#b0p0o280i0i0r1",
        "Recordings": "#b0p0o281i0i0r1"
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                accept_downloads=True,
                # FileMaker WebDirect needs a reasonably large viewport to render its layout
                # correctly even in headless mode — too small and panels collapse/hide.
                viewport={"width": 1440, "height": 900},
            )
            page = await context.new_page()

            print("Navigating to UARB Portal...")
            await page.goto("https://uarb.novascotia.ca/fmi/webd/UARB15")

            parent_selector = "#b0p0o254i0i0r1"
            await page.wait_for_selector(parent_selector)

            print(f"Entering Matter ID: {matter_id}")
            input_target = page.locator(parent_selector)

            # In headless mode click() still works for focused inputs since there is no
            # glass pane over the search field.
            await input_target.click()
            await page.wait_for_timeout(500)

            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(matter_id, delay=50)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            await page.wait_for_load_state("networkidle")

            target_tab_id = tab_selectors.get(doc_type)
            if target_tab_id:
                print(f"Switching to tab: {doc_type} ({target_tab_id})")
                await page.wait_for_selector(target_tab_id)
                await page.click(target_tab_id)
            else:
                print(f"Warning: Document type '{doc_type}' not found in selector map.")

            await page.wait_for_timeout(3000)
            print(f"Tab '{doc_type}' active. Starting virtualized scroll-and-scan loop...")

            downloaded_count = 0
            processed_ids = set()
            consecutive_empty_scrolls = 0
            MAX_EMPTY_SCROLLS = 5
            current_scroll_top = 0  # Accumulated scroll position for the Vaadin scroller

            while downloaded_count < max_downloads:
                # --- Scan: find all currently rendered "GO GET IT" buttons ---
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

                    print(f"[{downloaded_count + 1}] Clicking 'GO GET IT' (id={btn_id})...")

                    # In headless mode the browser has no physical display, so:
                    #   - btn.click() may fail with "outside of viewport" once Vaadin virtualizes
                    #     rows beyond the initially visible area.
                    #   - hover() + mouse.wheel() don't work without a real display.
                    #
                    # Solution: dispatch a full mousedown→mouseup→click event sequence directly
                    # on the element via JS. This has no viewport or hit-test requirements, and
                    # unlike a bare .click() it includes mousedown/mouseup which is what
                    # FileMaker's Vaadin runtime actually listens on to trigger actions.
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

                    result = await download_from_modal(page, download_dir)

                    # Defensive dismissal in case the modal close didn't fully complete.
                    try:
                        close_btn = page.locator(".v-slot-primary .v-button-primary")
                        if await close_btn.is_visible():
                            await close_btn.click()
                        await page.locator(".v-window-modalitycurtain").wait_for(state="hidden", timeout=3000)
                    except Exception:
                        pass

                    if result:
                        downloaded_count += 1

                if downloaded_count >= max_downloads:
                    print(f"Reached {max_downloads} downloads. Done.")
                    break

                if not new_buttons_found:
                    consecutive_empty_scrolls += 1
                    if consecutive_empty_scrolls >= MAX_EMPTY_SCROLLS:
                        print(f"No new rows after {MAX_EMPTY_SCROLLS} consecutive scrolls. End of list.")
                        break

                    print(f"No new buttons found (miss #{consecutive_empty_scrolls}). Scrolling via JS scrollTop...")

                    # .v-grid-scroller-vertical has width: 0px so it can't receive pointer events,
                    # and mouse.wheel() requires a real display. Directly mutate scrollTop and
                    # dispatch a scroll event so Vaadin's virtual row engine fetches the next batch.
                    SCROLL_STEP = 204  # 3 rows × 68px each
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

            print(f"Finished. Downloaded {downloaded_count} file(s) to '{download_dir}'.")
            await browser.close()

    except Exception as e:
        print(f"Error during search: {e}")


if __name__ == "__main__":
    print("\n--- Test: Headless traversal for M12205 Exhibits ---")
    asyncio.run(run_uarb_search("M12205", "Exhibits"))

    print("--- Test: Headless traversal for M12205 Other Documents ---")
    asyncio.run(run_uarb_search("M12205", "Other Documents"))
