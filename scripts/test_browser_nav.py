"""
Quick probe script to test Playwright interaction with Streamlit navigation.
"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8501", wait_until="networkidle")
    print("Page Title:", page.title())

    # Find navigation items
    nav_links = page.locator("[data-testid='stSidebarNav'] a, [data-testid='stSidebar'] a").all()
    print(f"Found {len(nav_links)} navigation links:")
    for link in nav_links:
        print(" - Text:", link.inner_text().replace("\n", " "), "Href:", link.get_attribute("href"))

    browser.close()
