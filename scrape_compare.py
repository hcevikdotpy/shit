import asyncio
import json
import re
from playwright_stealth import Stealth

LISTING_IDS = [
    "440029792", "457551621", "456333942", "457717885", "458711959",
    "458501356", "457988469", "414721913", "457434243", "457257293",
    "457229728", "442782174", "454899106", "452510888",
]

# Compare endpoint - try loading all at once and in pairs
COMPARE_ALL = "https://www.mobile.de/park/compare?id=" + "&id=".join(LISTING_IDS)

def parse_rsc_full(html):
    chunks = re.findall(r'self\.__next_f\.push\(\[(.*?)\]\)', html, re.DOTALL)
    full = ""
    for chunk in chunks:
        try:
            parsed = json.loads(f"[{chunk}]")
            if len(parsed) >= 2 and isinstance(parsed[1], str):
                full += parsed[1]
        except:
            pass
    return full

def dump_all_string_values(rsc, min_len=50):
    """Find all string values longer than min_len."""
    results = []
    i = 0
    while i < len(rsc):
        if rsc[i] == '"':
            j = i + 1
            chars = []
            while j < len(rsc):
                ch = rsc[j]
                if ch == '\\' and j+1 < len(rsc):
                    chars.append(rsc[j+1])
                    j += 2
                elif ch == '"':
                    break
                else:
                    chars.append(ch)
                    j += 1
            val = ''.join(chars)
            if len(val) >= min_len and not val.startswith('http') and not val.startswith('/_next'):
                results.append(val)
            i = j + 1
        else:
            i += 1
    return results

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

        print(f"Loading compare page with all {len(LISTING_IDS)} IDs...")
        resp = await page.goto(COMPARE_ALL, wait_until="domcontentloaded", timeout=40000)
        print(f"Status: {resp.status}")
        await page.wait_for_timeout(5000)

        html = await page.evaluate("() => document.documentElement.outerHTML")
        print(f"HTML: {len(html)} bytes")

        with open("/home/user/shit/page_compare.html", "w", encoding="utf-8") as f:
            f.write(html)

        title = await page.title()
        print(f"Title: {title}")

        rsc = parse_rsc_full(html)
        print(f"RSC: {len(rsc)} bytes")

        if len(html) > 20000:
            print("\nLooking for description-like strings...")
            long_strings = dump_all_string_values(rsc, min_len=80)
            for s in long_strings[:30]:
                print(f"  [{len(s)}] {s[:100]}")

        await browser.close()

asyncio.run(main())
