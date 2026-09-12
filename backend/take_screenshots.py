import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe")
        page = await browser.new_page()
        # Capture Chat
        await page.goto("http://localhost:5173/app")
        await page.wait_for_selector(".chat-window")
        await page.screenshot(path="e:/Servora/frontend/public/assets/chat-preview.png")
        
        # Click dashboard tab
        await page.click("button:has-text('Staff Dashboard')")
        await page.wait_for_selector("table")
        await page.screenshot(path="e:/Servora/frontend/public/assets/dashboard-preview.png")
        
        await browser.close()

asyncio.run(main())
