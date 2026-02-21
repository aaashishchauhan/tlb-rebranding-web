import sys
import logging
import time
from playwright.sync_api import sync_playwright

def fetch_thyrocare_pdf(url, output_path):
    """
    Fetches PDF from Thyrocare URL and saves to output_path.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [FETCHER] %(message)s")
    logger = logging.getLogger("FETCHER")
    
    logger.info(f"Fetching {url} -> {output_path}")

    for attempt in range(3):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    accept_downloads=True,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = context.new_page()
                
                try:
                    logger.info(f"Attempt {attempt+1}: Going to {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # Check for button
                    try:
                        page.wait_for_selector("text=Download Report", timeout=15000)
                    except:
                        logger.warning("Download button not found immediately.")

                    with page.expect_download(timeout=60000) as download_info:
                        page.click("text=Download Report")
                    
                    download = download_info.value
                    download.save_as(output_path)
                    logger.info(f"Success: {output_path}")
                    return True
                    
                finally:
                    context.close()
                    browser.close()
        except Exception as e:
            logger.error(f"Attempt {attempt+1} Failed: {e}")
            time.sleep(5) # Wait before retry
            
    return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fetch_url.py <URL> <OUTPUT_PATH>")
        sys.exit(1)
        
    url = sys.argv[1]
    out = sys.argv[2]
    
    success = fetch_thyrocare_pdf(url, out)
    sys.exit(0 if success else 1)
