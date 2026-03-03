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
        await modal.wait_for(state="visible", timeout=500)
        
        # 2. Use page.expect_download() context manager
        # 3. Click the button with class .fm-download-button
        async with page.expect_download() as download_info:
            await page.click('.fm-download-button')
        
        download = await download_info.value
        
        # 4. Save file to directory using suggested filename
        file_path = os.path.join(download_dir, download.suggested_filename)
        await download.save_as(file_path)
        print(f"Downloaded: {file_path}")
        
        # 5. Click the \"Close\" button inside that specific modal
        await page.locator('.v-button.primary:has-text("Close")').click()
        
        # 6. Wait for the modality curtain to disappear
        curtain = page.locator('.v-window-modalitycurtain')
        await curtain.wait_for(state="hidden", timeout=5000)
        
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

            # Wait for the "GO GET IT" buttons to become visible instead of relying on the table
            try:
                await page.locator('text="GO GET IT"').first.wait_for(state="visible", timeout=1500)
            except Exception as e:
                print("Warning: 'GO GET IT' buttons not found within timeout.")

            # Give the tab content an extra moment to fully bind JavaScript event handlers
            await page.wait_for_timeout(3000)
            
            print(f"Tab {doc_type} active. Searching for 'GO GET IT' elements...")
            
            # Use exact text selector; We don't restrict to 'table' because some document tabs might render differently
            download_elements = await page.locator('text="GO GET IT"').all()
            print(f"Found {len(download_elements)} 'GO GET IT' elements.")
            
            max_downloads = min(10, len(download_elements))
            for i in range(max_downloads):
                print(f"[{i + 1}] Clicking 'GO GET IT' button...")
                
                # FileMaker renders its list inside a custom scrollable container div, not the window.
                # We walk up the DOM to find that overflow container and scroll the button into it.
                await download_elements[i].evaluate("""node => {
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
                    // Fallback: standard scrollIntoView
                    node.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }""")
                await page.wait_for_timeout(600) # wait for smooth scroll to settle
                
                await download_elements[i].click(delay=100)
                
                # Handle the FileMaker modal download
                await download_from_modal(page, download_dir)
            
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
        