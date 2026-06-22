import asyncio
import json
import re
from playwright_stealth import Stealth

LISTING_IDS = [
    "440029792", "457551621", "456333942", "457717885", "458711959",
    "458501356", "457988469", "414721913", "457434243", "457257293",
    "457229728", "442782174", "454899106", "452510888",
]

PARK_URL = "https://www.mobile.de/park/list?id=" + "&id=".join(LISTING_IDS)

API_RESPONSES = {}

async def main():
    from playwright.async_api import async_playwright

    stealth = Stealth(
        navigator_languages_override=("de-DE", "de"),
        navigator_platform_override="iPhone",
    )

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

        async def on_response(response):
            url = response.url
            if 'mobile.de/api' in url:
                try:
                    body = await response.body()
                    API_RESPONSES[url] = body.decode('utf-8', errors='replace')
                    print(f"API: {url[:100]} -> {len(body)} bytes")
                except:
                    pass

        page.on("response", on_response)

        print("Loading park list...")
        await page.goto(PARK_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(5000)

        # Get request headers from the page to use for direct API calls
        headers_js = await page.evaluate("""() => {
            return {
                'user-agent': navigator.userAgent,
                'accept-language': navigator.language,
            }
        }""")
        print(f"\nPage headers: {headers_js}")

        # Get all cookies
        cookies = await context.cookies()
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        print(f"\nCookies ({len(cookies)}): {cookie_str[:200]}...")

        # Now try direct API calls for individual vehicle details using fetch from page context
        print("\n=== Probing API endpoints ===")
        test_id = LISTING_IDS[0]

        # Try various API patterns
        endpoints = [
            f"https://www.mobile.de/api/r/vehicles/{test_id}",
            f"https://www.mobile.de/api/r/ads/{test_id}",
            f"https://www.mobile.de/api/r/listings/{test_id}",
            f"https://www.mobile.de/api/r/ad/{test_id}",
            f"https://www.mobile.de/api/r/vehicle/{test_id}",
            f"https://www.mobile.de/api/r/inserat/{test_id}?_lang=de",
            f"https://www.mobile.de/api/r/search/vehicle?id={test_id}",
            f"https://www.mobile.de/api/r/search/car/{test_id}",
            f"https://www.mobile.de/api/v1/vehicle/{test_id}",
            f"https://www.mobile.de/api/v2/ad/{test_id}",
        ]

        for ep in endpoints:
            try:
                resp = await page.evaluate(f"""async () => {{
                    try {{
                        const r = await fetch('{ep}', {{
                            headers: {{
                                'accept': 'application/json',
                                'accept-language': 'de-DE,de;q=0.9',
                            }}
                        }});
                        const text = await r.text();
                        return {{ status: r.status, body: text.substring(0, 200) }};
                    }} catch(e) {{
                        return {{ error: e.message }};
                    }}
                }}""")
                print(f"  {ep.split('mobile.de')[1]:<50} -> {resp}")
            except Exception as e:
                print(f"  {ep.split('mobile.de')[1]:<50} -> ERROR: {e}")

        await browser.close()

    # Save captured API responses
    for url, body in API_RESPONSES.items():
        print(f"\n=== {url} ===")
        print(body[:500])

asyncio.run(main())
