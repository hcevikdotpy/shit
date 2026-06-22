import asyncio
import json
import re
from playwright_stealth import Stealth

async def main():
    from playwright.async_api import async_playwright

    url = "https://www.mobile.de/park/list?id=440029792&id=457551621&id=456333942&id=457717885&id=458711959&id=458501356&id=457988469&id=414721913&id=457434243&id=457257293&id=457229728&id=442782174&id=454899106&id=452510888"

    stealth = Stealth(
        navigator_languages_override=("de-DE", "de"),
        navigator_platform_override="iPhone",
    )

    async with stealth.use_async(async_playwright()) as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/21A329 mobile.de/8.2",
            viewport={"width": 390, "height": 844},
            locale="de-DE",
            is_mobile=True,
        )
        page = await context.new_page()

        print(f"Navigating to watchlist...")
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        print(f"Status: {resp.status}")
        # Wait longer for JS to settle
        await page.wait_for_timeout(6000)

        # Use evaluate to get HTML from within the page context
        html = await page.evaluate("() => document.documentElement.outerHTML")
        print(f"HTML length: {len(html)}")

        with open("/home/user/shit/page_dump3.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Saved page_dump3.html")

        await browser.close()

asyncio.run(main())
