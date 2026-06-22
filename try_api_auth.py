import asyncio
import json
from playwright_stealth import Stealth

PARK_URL = "https://www.mobile.de/park/list?id=440029792&id=457551621&id=456333942"
TEST_ID = "440029792"

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
        await page.goto(PARK_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(3000)

        cookies = await context.cookies()
        vi_token = next((c['value'] for c in cookies if c['name'] == 'vi'), None)
        print(f"vi token: {vi_token[:80] if vi_token else 'NOT FOUND'}...")

        # Try API with various auth methods
        endpoints = [
            f"https://www.mobile.de/api/r/vehicles/{TEST_ID}",
            f"https://www.mobile.de/api/r/ads/{TEST_ID}?_lang=de",
            f"https://www.mobile.de/api/r/park/details?id={TEST_ID}",
            f"https://www.mobile.de/api/r/park/detail?id={TEST_ID}",
            f"https://www.mobile.de/api/r/park/list?id={TEST_ID}",
            f"https://www.mobile.de/api/r/watchlist?id={TEST_ID}",
        ]

        for ep in endpoints:
            ep_path = ep.split('mobile.de')[1]
            # Try with vi as Bearer
            r = await page.evaluate(f"""async () => {{
                const r1 = await fetch('{ep}', {{
                    credentials: 'include',
                    headers: {{
                        'Authorization': 'Bearer {vi_token}',
                        'accept': 'application/json',
                        'accept-language': 'de-DE,de;q=0.9',
                    }}
                }}).catch(e => null);
                if (!r1) return {{ error: 'fetch failed' }};
                const t = await r1.text();
                return {{ status: r1.status, len: t.length, body: t.substring(0, 150) }};
            }}""")
            print(f"  {ep_path[:55]:<55} -> {r.get('status')} {r.get('body', r.get('error', ''))[:80]}")

        await browser.close()

asyncio.run(main())
