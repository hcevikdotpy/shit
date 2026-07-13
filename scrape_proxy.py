import asyncio, json, re, os
from playwright_stealth import Stealth

LID = "459397539"
PROXY = os.environ.get("HTTPS_PROXY", "")

def parse_rsc(html):
    chunks = re.findall(r'self\.__next_f\.push\(\[(.*?)\]\)', html, re.DOTALL)
    full = ""
    for chunk in chunks:
        try:
            p = json.loads(f"[{chunk}]")
            if len(p) >= 2 and isinstance(p[1], str):
                full += p[1]
        except: pass
    return full

async def main():
    from playwright.async_api import async_playwright
    stealth = Stealth(navigator_languages_override=("de-DE","de"), navigator_platform_override="iPhone")

    proxy_conf = None
    if PROXY:
        # Parse proxy URL
        from urllib.parse import urlparse
        p = urlparse(PROXY)
        proxy_conf = {"server": f"{p.scheme}://{p.hostname}:{p.port}"}
        print(f"Using proxy: {proxy_conf}")

    async with stealth.use_async(async_playwright()) as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            proxy=proxy_conf,
        )
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/21A329 mobile.de/8.2",
            viewport={"width": 390, "height": 844},
            locale="de-DE",
            is_mobile=True,
        )
        page = await context.new_page()

        for url in [
            f"https://www.mobile.de/park/list?id={LID}",
            f"https://www.mobile.de/park/compare?id={LID}",
        ]:
            label = "list" if "list" in url else "compare"
            print(f"\nLoading {label}...")
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                await page.wait_for_timeout(5000)
                html = await page.evaluate("() => document.documentElement.outerHTML")
                status = resp.status if resp else 0
                print(f"  Status: {status}, HTML: {len(html)} bytes")
                with open(f"/home/user/shit/single_{label}.html", "w", encoding="utf-8") as f:
                    f.write(html)
                rsc = parse_rsc(html)
                print(f"  RSC: {len(rsc)} bytes, title: {await page.title()}")
            except Exception as e:
                print(f"  Error: {e}")
            await asyncio.sleep(3)

        await browser.close()

asyncio.run(main())
