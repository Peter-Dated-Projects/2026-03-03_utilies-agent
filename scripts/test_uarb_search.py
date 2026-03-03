import re
import os
import uuid
import shutil
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
        # 1. Wait for modal to be visible - if it doesn't appear quickly,
        # it usually means the file is invalid/missing on FileMaker's end.
        modal = page.locator('.fm-modal-dialog')
        await modal.wait_for(state="visible", timeout=5000)
        
        # 2. Use page.expect_download() context manager
        # 3. Click the button with class .fm-download-button
        async with page.expect_download() as download_info:
            await page.click('.fm-download-button')
        
        download = await download_info.value
        
        # 4. Save file to directory using suggested filename
        file_path = os.path.join(download_dir, download.suggested_filename)
        await download.save_as(file_path)
        print(f"Downloaded: {file_path}")
        
        # 5. Click the Close button via its stable structural selector
        await page.click(".v-slot-primary .v-button-primary")
        
        # 6. Wait for the modality curtain to disappear - CRITICAL before next click
        await page.locator(".v-window-modalitycurtain").wait_for(state="hidden")
        
        return file_path
    except Exception as e:
        print(f"Error downloading from modal: {e}")
        return None

async def run_uarb_search(matter_id, doc_type):
    job_id = str(uuid.uuid4())
    download_dir = os.path.join("assets", job_id)
    os.makedirs(download_dir, exist_ok=True)
    print(f"Job Initialized. Temporary directory: {download_dir}")

    # Map document types to the specific IDs you found
    tab_selectors = {
        "Exhibits": "#b0p0o277i0i0r1",
        "Key Documents": "#b0p0o278i0i0r1",
        "Other Documents": "#b0p0o279i0i0r1",
        "Transcripts": "#b0p0o280i0i0r1",
        "Recordings": "#b0p0o281i0i0r1"
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False) 
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()

            print(f"Navigating to UARB Portal...")
            await page.goto("https://uarb.novascotia.ca/fmi/webd/UARB15")

            # Wait for the FileMaker app to initialize
            parent_selector = "#b0p0o254i0i0r1"
            await page.wait_for_selector(parent_selector)

            print(f"Entering Matter ID: {matter_id}")
            # Target the input field more robustly; FileMaker often uses `input` inside `.text` wrapper
            input_target = page.locator(f"{parent_selector}")
            
            # Click to focus, wait for FileMaker to swap in the actual HTML input element
            await input_target.click()
            await page.wait_for_timeout(500)
            
            await page.keyboard.press("Control+A") # Select all text
            await page.keyboard.press("Backspace") # Delete it
            await page.keyboard.type(matter_id, delay=50) # Type the new value in slowly so FileMaker registers it
            
            # Press enter and wait a moment to ensure FileMaker commits the field value to its backend
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)

            # Wait for results page to load
            await page.wait_for_load_state("networkidle")

            # Navigate to the specific tab requested by the user
            target_tab_id = tab_selectors.get(doc_type)
            if target_tab_id:
                print(f"Switching to tab: {doc_type} ({target_tab_id})")
                await page.wait_for_selector(target_tab_id)
                await page.click(target_tab_id)
            else:
                print(f"Warning: Document type '{doc_type}' not found in selector map.")

            # Give the tab content a moment to fully bind JavaScript event handlers
            await page.wait_for_timeout(3000)
            print(f"Tab '{doc_type}' active. Starting virtualized scroll-and-scan loop...")

            MAX_DOWNLOADS = 10
            downloaded_count = 0
            processed_ids = set()   # Track button IDs already handled
            consecutive_empty_scrolls = 0  # End-of-list guard
            MAX_EMPTY_SCROLLS = 5          # Stop after 5 scrolls with no new buttons
            current_scroll_top = 0         # Track accumulated scroll position

            while downloaded_count < MAX_DOWNLOADS:
                # --- Guard: ensure no modal curtain is blocking the grid before each iteration ---
                try:
                    curtain = page.locator(".v-window-modalitycurtain")
                    if await curtain.is_visible():
                        # Try to close via the primary button if it's still showing
                        close_btn = page.locator(".v-slot-primary .v-button-primary")
                        if await close_btn.is_visible():
                            await close_btn.click()
                        await curtain.wait_for(state="hidden", timeout=3000)
                except Exception:
                    pass  # Curtain wasn't present or already dismissed

                # --- Scan: find all currently rendered "GO GET IT" buttons ---
                buttons = await page.get_by_role("button", name="GO GET IT").all()

                new_buttons_found = False
                for btn in buttons:
                    if downloaded_count >= MAX_DOWNLOADS:
                        break

                    btn_id = await btn.get_attribute("id")

                    # Skip buttons we've already processed (or ones with no id)
                    if btn_id is None or btn_id in processed_ids:
                        continue

                    processed_ids.add(btn_id)
                    new_buttons_found = True
                    consecutive_empty_scrolls = 0  # Reset miss counter on any new find

                    print(f"[{downloaded_count + 1}] Clicking 'GO GET IT' (id={btn_id})...")
                    # Dispatch a full mousedown→mouseup→click sequence via JS.
                    # - force=True was tried but fails when the element is outside the browser
                    #   viewport (Vaadin virtualizes rows below the visible grid fold).
                    # - JS bare .click() was tried but FileMaker ignores it (listens on mousedown).
                    # - This approach has no viewport or hit-test requirements and includes
                    #   mousedown/mouseup which Vaadin's button handler actually responds to.
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

                    # Download the file from the modal
                    result = await download_from_modal(page, download_dir)

                    # Defensively dismiss any residual modal/overlay before continuing.
                    # Use a longer timeout here — 500ms was too tight for the close animation.
                    try:
                        close_btn = page.locator(".v-slot-primary .v-button-primary")
                        if await close_btn.is_visible():
                            await close_btn.click()
                        await page.locator(".v-window-modalitycurtain").wait_for(state="hidden", timeout=3000)
                    except Exception:
                        pass  # Modal was already gone, continue

                    if result:
                        downloaded_count += 1

                if downloaded_count >= MAX_DOWNLOADS:
                    print(f"Reached {MAX_DOWNLOADS} downloads. Done.")
                    break

                if not new_buttons_found:
                    consecutive_empty_scrolls += 1
                    if consecutive_empty_scrolls >= MAX_EMPTY_SCROLLS:
                        print(f"No new rows after {MAX_EMPTY_SCROLLS} consecutive scrolls. End of list.")
                        break

                    print(f"No new buttons found (miss #{consecutive_empty_scrolls}). Scrolling via JS scrollTop...")

                    # .v-grid-scroller-vertical has width: 0px, so Playwright's mouse.wheel()
                    # and hover-based wheel events cannot hit it / are ignored by Vaadin.
                    # The correct approach: directly mutate scrollTop on the internal scroller
                    # element via JS and dispatch a 'scroll' event so Vaadin's virtual row
                    # engine detects the change and fetches the next batch of rows.
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

                    # Wait for Vaadin to fetch and render the new rows
                    await page.wait_for_timeout(1500)

            print(f"Finished. Downloaded {downloaded_count} file(s) to '{download_dir}'.")
            
            # await browser.close()
    except Exception as e:
        print(f"Error during search: {e}")

if __name__ == "__main__":
    print("\\n--- Test 2: Specific traversal for M12205 and Exhibits ---")
    matter_exhibits = "M12205"
    doc_type_exhibits = "Exhibits"
    asyncio.run(run_uarb_search(matter_exhibits, doc_type_exhibits))

    # Test simulation 1
    print("--- Test 1 ---")
    user_query = "Hi Agent, Can you give me Other Documents files from M12205? Thanks!"
    matter = extract_matter_id(user_query)
    
    # Simple logic to find the doc_type keyword in the query
    requested_doc_type = "Other Documents" # In production, match this from your VALID_DOC_TYPES list
    
    if matter:
        asyncio.run(run_uarb_search(matter, requested_doc_type))
        