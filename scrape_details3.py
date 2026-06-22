import asyncio
import json
import re
from playwright_stealth import Stealth

LISTING_IDS = [
    "440029792", "457551621", "456333942", "457717885", "458711959",
    "458501356", "457988469", "414721913", "457434243", "457257293",
    "457229728", "442782174", "454899106", "452510888",
]

PARK_URL = "https://www.mobile.de/park/list?id=440029792&id=457551621&id=456333942&id=457717885&id=458711959&id=458501356&id=457988469&id=414721913&id=457434243&id=457257293&id=457229728&id=442782174&id=454899106&id=452510888"

async def extract_listing_data(page, listing_id, url):
    result = {"id": listing_id, "url": url}
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        result["http_status"] = resp.status if resp else 0
        if resp and resp.status >= 400:
            result["error"] = f"HTTP {resp.status}"
            return result

        await page.wait_for_timeout(4000)

        html = await page.evaluate("() => document.documentElement.outerHTML")
        result["html_length"] = len(html)

        # Check for blocks
        title = await page.title()
        result["page_title"] = title
        if "403" in title or "blocked" in title.lower() or "captcha" in title.lower():
            result["error"] = f"Blocked: {title}"
            return result

        # --- Try RSC data extraction first ---
        next_f_chunks = re.findall(r'self\.__next_f\.push\(\[(.*?)\]\)', html, re.DOTALL)
        full_data = ""
        for chunk in next_f_chunks:
            try:
                parsed = json.loads(f"[{chunk}]")
                if len(parsed) >= 2 and isinstance(parsed[1], str):
                    full_data += parsed[1]
            except:
                pass

        if full_data:
            result["rsc_length"] = len(full_data)
            # Extract description
            for desc_key in ['"description":', '"freeText":', '"text":', '"beschreibung":', '"freitext":']:
                idx = full_data.lower().find(desc_key.lower())
                if idx != -1:
                    # grab the string value after the key
                    val_start = full_data.find('"', idx + len(desc_key))
                    if val_start != -1:
                        val_end = val_start + 1
                        while val_end < len(full_data):
                            if full_data[val_end] == '"' and full_data[val_end-1] != '\\':
                                break
                            val_end += 1
                        desc_val = full_data[val_start+1:val_end]
                        if len(desc_val) > 20:
                            result["description"] = desc_val
                            break

            # Extract features/equipment array
            for feat_key in ['"features":', '"equipment":', '"ausstattung":', '"highlights":', '"featureList":']:
                idx = full_data.lower().find(feat_key.lower())
                if idx != -1:
                    arr_start = full_data.find('[', idx + len(feat_key))
                    if arr_start != -1:
                        depth = 0
                        arr_end = arr_start
                        for i, ch in enumerate(full_data[arr_start:arr_start+50000]):
                            if ch in '[{': depth += 1
                            elif ch in ']}':
                                depth -= 1
                                if depth == 0:
                                    arr_end = arr_start + i + 1
                                    break
                        try:
                            features = json.loads(full_data[arr_start:arr_end])
                            if features:
                                result["features_raw"] = features
                                break
                        except:
                            pass

        # --- DOM-based extraction ---
        # Description text
        desc_selectors = [
            "[data-testid='listing-description']",
            ".listing-description",
            "[class*='description']",
            ".g-description",
            "#listing-description",
            "section[aria-label*='Beschreibung']",
            "section[aria-label*='description']",
        ]
        for sel in desc_selectors:
            el = page.locator(sel).first
            if await el.count() > 0:
                txt = (await el.inner_text()).strip()
                if len(txt) > 20:
                    result["description_dom"] = txt
                    break

        # Equipment / features
        equip_selectors = [
            "[data-testid='listing-features']",
            ".listing-features",
            "[class*='features']",
            ".g-features",
            "[data-testid='equipment']",
            "section[aria-label*='Ausstattung']",
            "[class*='equipment']",
        ]
        for sel in equip_selectors:
            el = page.locator(sel).first
            if await el.count() > 0:
                txt = (await el.inner_text()).strip()
                if len(txt) > 10:
                    result["equipment_dom"] = txt
                    break

        # Full page text as fallback
        body_text = await page.locator("body").inner_text()
        lines = [l.strip() for l in body_text.split("\n") if l.strip() and len(l.strip()) > 2]
        result["page_lines_count"] = len(lines)
        result["page_text_sample"] = lines[:200]

    except Exception as e:
        result["error"] = str(e)

    return result


async def main():
    stealth = Stealth(
        navigator_languages_override=("de-DE", "de"),
        navigator_platform_override="iPhone",
    )

    async with stealth.use_async(__import__('playwright.async_api', fromlist=['async_playwright']).async_playwright()) as p:
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

        # Warm up: load park list to get cookies/session
        print("Loading park list for session cookies...")
        await page.goto(PARK_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(3000)
        print("Park list loaded. Starting individual listings...")

        results = []
        for i, lid in enumerate(LISTING_IDS):
            # Try the auto-inserat URL format first (from the RSC data)
            url = f"https://suchen.mobile.de/fahrzeuge/details.html?id={lid}"
            print(f"\n[{i+1}/{len(LISTING_IDS)}] Scraping {lid}...")
            data = await extract_listing_data(page, lid, url)
            status = data.get("http_status", "?")
            html_len = data.get("html_length", 0)
            rsc_len = data.get("rsc_length", 0)
            err = data.get("error", "")
            desc_preview = (data.get("description") or data.get("description_dom") or "")[:60]
            equip_count = len(data.get("features_raw") or [])
            print(f"  status={status} html={html_len} rsc={rsc_len} eq={equip_count} desc='{desc_preview}' err={err}")
            results.append(data)

            if i < len(LISTING_IDS) - 1:
                await page.wait_for_timeout(2500)

        await browser.close()

    with open("/home/user/shit/details3.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nDone. Saved {len(results)} to details3.json")

asyncio.run(main())
