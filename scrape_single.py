import asyncio, json, re
from playwright_stealth import Stealth

LID = "459397539"
PARK_URL = f"https://www.mobile.de/park/list?id={LID}"
COMPARE_URL = f"https://www.mobile.de/park/compare?id={LID}"

def parse_rsc(html):
    chunks = re.findall(r'self\.__next_f\.push\(\[(.*?)\]\)', html, re.DOTALL)
    full = ""
    for chunk in chunks:
        try:
            parsed = json.loads(f"[{chunk}]")
            if len(parsed) >= 2 and isinstance(parsed[1], str):
                full += parsed[1]
        except: pass
    return full

async def fetch_page(page, url):
    resp = await page.goto(url, wait_until="domcontentloaded", timeout=40000)
    await page.wait_for_timeout(5000)
    html = await page.evaluate("() => document.documentElement.outerHTML")
    return resp.status, html

async def main():
    from playwright.async_api import async_playwright
    stealth = Stealth(navigator_languages_override=("de-DE","de"), navigator_platform_override="iPhone")

    async with stealth.use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/21A329 mobile.de/8.2",
            viewport={"width": 390, "height": 844},
            locale="de-DE",
            is_mobile=True,
        )
        page = await context.new_page()

        print("Loading park list...")
        status, html = await fetch_page(page, PARK_URL)
        print(f"Park list: {status}, {len(html)} bytes")
        with open("/home/user/shit/single_park.html", "w", encoding="utf-8") as f:
            f.write(html)

        await page.wait_for_timeout(2000)

        print("Loading compare page...")
        status2, html2 = await fetch_page(page, COMPARE_URL)
        print(f"Compare: {status2}, {len(html2)} bytes")
        with open("/home/user/shit/single_compare.html", "w", encoding="utf-8") as f:
            f.write(html2)

        await browser.close()

asyncio.run(main())
