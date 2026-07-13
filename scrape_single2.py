import asyncio, json, re, time
from playwright_stealth import Stealth

LID = "459397539"

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

async def fetch_with_retry(page, url, retries=3):
    for attempt in range(retries):
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)
            html = await page.evaluate("() => document.documentElement.outerHTML")
            return resp.status if resp else 0, html
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(4)
    return 0, ""

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

        # Start with homepage to warm up
        print("Warming up on mobile.de homepage...")
        try:
            await page.goto("https://www.mobile.de", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            print(f"  Homepage: {await page.title()}")
        except Exception as e:
            print(f"  Homepage failed: {e}")

        # Park list
        print(f"\nLoading park/list for {LID}...")
        status, html = await fetch_with_retry(page, f"https://www.mobile.de/park/list?id={LID}")
        print(f"  Status: {status}, HTML: {len(html)} bytes")
        if html:
            with open("/home/user/shit/single_park.html", "w", encoding="utf-8") as f:
                f.write(html)
            rsc = parse_rsc(html)
            print(f"  RSC: {len(rsc)} bytes")

        await asyncio.sleep(3)

        # Compare page
        print(f"\nLoading park/compare for {LID}...")
        status2, html2 = await fetch_with_retry(page, f"https://www.mobile.de/park/compare?id={LID}")
        print(f"  Status: {status2}, HTML: {len(html2)} bytes")
        if html2:
            with open("/home/user/shit/single_compare.html", "w", encoding="utf-8") as f:
                f.write(html2)
            rsc2 = parse_rsc(html2)
            print(f"  RSC: {len(rsc2)} bytes")

        await browser.close()

asyncio.run(main())
