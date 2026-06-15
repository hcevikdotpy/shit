import asyncio
import json
import random
from playwright.async_api import async_playwright

LISTING_IDS = [
    "457314103", "456303371", "457346164", "455982574", "457761820",
    "453436024", "449587173", "458289271", "456722503", "456798000",
    "458319975", "456438375", "444296226", "456609961", "457352622",
    "452454491", "455027252", "456346875", "453003833", "449890047",
    "447962998",
]

def make_url(listing_id):
    return f"https://suchen.mobile.de/fahrzeuge/details.html?id={listing_id}"

async def accept_cookies(page):
    try:
        btn = page.locator("button[data-testid='as-CookieBanner-AcceptAllButton']")
        if await btn.count() > 0:
            await btn.click()
            await page.wait_for_timeout(500)
            return
        # fallback: any "Alle akzeptieren" button
        for text in ["Alle akzeptieren", "Accept all", "Akzeptieren"]:
            btn = page.get_by_text(text, exact=True)
            if await btn.count() > 0:
                await btn.first.click()
                await page.wait_for_timeout(500)
                return
    except Exception:
        pass

async def extract_listing(page, listing_id):
    url = make_url(listing_id)
    result = {"id": listing_id, "url": url}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(random.randint(1500, 2500))
        await accept_cookies(page)
        await page.wait_for_timeout(500)

        # Check for block/error page
        title = await page.title()
        if "403" in title or "blocked" in title.lower() or "captcha" in title.lower():
            result["error"] = f"Blocked: {title}"
            return result

        content = await page.content()
        if "captcha" in content.lower() and len(content) < 5000:
            result["error"] = "CAPTCHA detected"
            return result

        # --- Price ---
        for sel in [
            "[data-testid='listing-price']",
            ".price-block__price",
            "[class*='price']",
            "h2[class*='price']",
        ]:
            el = page.locator(sel).first
            if await el.count() > 0:
                result["price"] = (await el.inner_text()).strip()
                break

        # --- Title / make + model ---
        for sel in [
            "h1[data-testid='listing-title']",
            ".listing-title",
            "h1",
        ]:
            el = page.locator(sel).first
            if await el.count() > 0:
                result["title"] = (await el.inner_text()).strip()
                break

        # --- Key facts table ---
        # mobile.de renders specs as label/value pairs
        specs = {}
        rows = page.locator("[data-testid='listing-details'] li, .g-col-6, .listing-details__item")
        count = await rows.count()
        for i in range(count):
            row = rows.nth(i)
            text = (await row.inner_text()).strip()
            if ":" in text:
                k, _, v = text.partition(":")
                specs[k.strip()] = v.strip()
            elif "\n" in text:
                parts = text.split("\n", 1)
                specs[parts[0].strip()] = parts[1].strip()

        if specs:
            result["specs"] = specs

        # --- Fallback: grab full page text for manual parsing ---
        if not specs:
            body_text = await page.locator("body").inner_text()
            # Extract relevant lines
            lines = [l.strip() for l in body_text.split("\n") if l.strip()]
            result["raw_lines"] = lines[:120]

    except Exception as e:
        result["error"] = str(e)

    return result


async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="de-DE",
            timezone_id="Europe/Berlin",
        )
        # Remove webdriver flag
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()

        # Warm up with homepage first to get cookies
        print("Warming up with mobile.de homepage...")
        try:
            await page.goto("https://www.mobile.de", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)
            await accept_cookies(page)
            await page.wait_for_timeout(1000)
        except Exception as e:
            print(f"Warmup failed: {e}")

        for i, listing_id in enumerate(LISTING_IDS):
            print(f"[{i+1}/{len(LISTING_IDS)}] Scraping {listing_id}...")
            data = await extract_listing(page, listing_id)
            results.append(data)
            print(f"  -> title: {data.get('title', 'N/A')[:60]}  price: {data.get('price', 'N/A')}")
            if i < len(LISTING_IDS) - 1:
                await page.wait_for_timeout(random.randint(2000, 4000))

        await browser.close()

    with open("/home/user/shit/listings.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Saved {len(results)} listings to listings.json")
    return results

asyncio.run(main())
