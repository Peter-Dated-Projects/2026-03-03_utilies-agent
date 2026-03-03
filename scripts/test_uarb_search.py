import re
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

async def run_uarb_search(matter_id, doc_type):
    # Map document types to the specific IDs you found
    tab_selectors = {
        "Exhibits": "#b0p0o277i0i0r1",
        "Key Documents": "#b0p0o278i0i0r1",
        "Other Documents": "#b0p0o279i0i0r1",
        "Transcripts": "#b0p0o280i0i0r1",
        "Recordings": "#b0p0o281i0i0r1"
    }

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
        input_target = page.locator(f"{parent_selector} > div >> .text")
        await input_target.click()
        await page.keyboard.type(matter_id)

        print("Clicking Search...")
        await page.click("#b0p0o258i0i0r1")

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

        # Wait for the table to appear (FileMaker web direct usually has one main data table)
        try:
            await page.wait_for_selector("table", timeout=10000)
        except Exception as e:
            print("Warning: Table not found within timeout.")

        # Give the tab content a moment to refresh and render rows
        await page.wait_for_timeout(2000)
        
        print(f"Tab {doc_type} active. Searching table for 'GO GET IT' elements...")
        
        # Use exact text selector scoped to the table; Playwright will target the innermost element
        download_elements = await page.locator('table >> text="GO GET IT"').all()
        print(f"Found {len(download_elements)} 'GO GET IT' elements.")
        
        for i, elem in enumerate(download_elements):
            # Attempt to extract an href from the element or its ancestors
            # This avoids hardcoding the exact div/span DOM tree
            url = await elem.evaluate('''node => {
                let current = node;
                while (current && current !== document.body) {
                    if (current.tagName === 'A' && current.hasAttribute('href')) {
                        return current.getAttribute('href');
                    }
                    if (current.hasAttribute && current.hasAttribute('href')) {
                        return current.getAttribute('href');
                    }
                    current = current.parentNode;
                }
                return null;
            }''')
            
            if url:
                print(f"[{i + 1}] PDF URL found: {url}")
            else:
                print(f"[{i + 1}] PDF URL not found directly in DOM (likely uses JS onclick/download).")
        
        # await browser.close()

if __name__ == "__main__":
    # Test simulation 1
    print("--- Test 1 ---")
    user_query = "Hi Agent, Can you give me Other Documents files from M12205? Thanks!"
    matter = extract_matter_id(user_query)
    
    # Simple logic to find the doc_type keyword in the query
    requested_doc_type = "Other Documents" # In production, match this from your VALID_DOC_TYPES list
    
    if matter:
        asyncio.run(run_uarb_search(matter, requested_doc_type))
        
    print("\n--- Test 2: Specific traversal for M12205 and Exhibits ---")
    matter_exhibits = "M12205"
    doc_type_exhibits = "Exhibits"
    asyncio.run(run_uarb_search(matter_exhibits, doc_type_exhibits))
