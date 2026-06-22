import asyncio
import json
import re
from playwright_stealth import Stealth

PARK_URL = "https://www.mobile.de/park/list?id=440029792&id=457551621&id=456333942&id=457717885&id=458711959&id=458501356&id=457988469&id=414721913&id=457434243&id=457257293&id=457229728&id=442782174&id=454899106&id=452510888"

async def main():
    from playwright.async_api import async_playwright

    stealth = Stealth(
        navigator_languages_override=("de-DE", "de"),
        navigator_platform_override="iPhone",
    )

    api_calls = []

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

        # Intercept all requests
        async def on_request(request):
            url = request.url
            if any(x in url for x in ['api', 'graphql', 'fahrzeug', 'listing', 'search', 'vehicle', 'inserat', 'details']):
                api_calls.append({
                    "method": request.method,
                    "url": url,
                    "headers": dict(request.headers),
                })

        async def on_response(response):
            url = response.url
            if any(x in url for x in ['api', 'graphql', 'fahrzeug', 'listing', 'search', 'vehicle', 'inserat', 'details']):
                try:
                    ct = response.headers.get('content-type', '')
                    if 'json' in ct or 'javascript' in ct:
                        body = await response.body()
                        if len(body) > 100:
                            print(f"RESPONSE {response.status} {url[:100]}")
                            print(f"  Content-Type: {ct}")
                            print(f"  Size: {len(body)}")
                            snippet = body.decode('utf-8', errors='replace')[:300]
                            print(f"  Body: {snippet}")
                            print()
                except:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        print(f"Loading park list...")
        await page.goto(PARK_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(5000)

        print("\n=== ALL INTERCEPTED API CALLS ===")
        for c in api_calls:
            print(f"  {c['method']} {c['url'][:120]}")

        await browser.close()

asyncio.run(main())
