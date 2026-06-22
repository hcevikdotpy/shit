import asyncio
import json
import re
from playwright_stealth import Stealth

LISTINGS = [
    ("440029792", "https://www.mobile.de/auto-inserat/renault-captur-luxe-1-2-aut-navi-r-cam-szh-8xlmf-temp-hu-zwickau/440029792.html"),
    ("457551621", "https://www.mobile.de/auto-inserat/mercedes-benz-c-180-c-coupe-c-180-cgi-blueefficiency-t%C3%BCv-neu-krostitz/457551621.html"),
    ("456333942", "https://www.mobile.de/auto-inserat/hyundai-i20-1-4-style-aut-klima-pdc-freispr-alus-t%C3%BCv-neu-berlin/456333942.html"),
    ("457717885", "https://www.mobile.de/auto-inserat/bmw-116-1-limousine-automatik-schiebedach-leder-berlin/457717885.html"),
    ("458711959", "https://www.mobile.de/auto-inserat/audi-a5-sportback-1-8-tfsi-bi-xenon-aac-pdc-shz-19z-brehna/458711959.html"),
    ("458501356", "https://www.mobile.de/auto-inserat/audi-a3-1-8-tfsi-sportback-aut-steuerkette-neu-1hand-berlin/458501356.html"),
    ("457988469", "https://www.mobile.de/auto-inserat/bmw-118i-f20-sport-line-led-automatik-wenig-km-berlin/457988469.html"),
    ("414721913", "https://www.mobile.de/auto-inserat/bmw-116-i-lim-5-trg-automatik-pdc-klima-berlin/414721913.html"),
    ("457434243", "https://www.mobile.de/auto-inserat/bmw-320-i-limousine-navi-bixenon-leder-pdc-tempomat-berlin/457434243.html"),
    ("457257293", "https://www.mobile.de/auto-inserat/bmw-116-i-automatik-pdc-2-hand-allwetter-nauen/457257293.html"),
    ("457229728", "https://www.mobile.de/auto-inserat/bmw-118-i-limousine-urban-autom-xen-klima-pdc-shz-sch%C3%B6nefeld-ot-gro%C3%9Fziethen/457229728.html"),
    ("442782174", "https://www.mobile.de/auto-inserat/audi-a3-quattro-lim-berlin/442782174.html"),
    ("454899106", "https://www.mobile.de/auto-inserat/kia-rio-spirit-automatik-kamera-tempomat-sitzheizung-sch%C3%B6neiche-bei-berlin/454899106.html"),
    ("452510888", "https://www.mobile.de/auto-inserat/bmw-116-116-i-xenon-automatik-ahk-2-hand-brandenburg/452510888.html"),
]

PARK_URL = "https://www.mobile.de/park/list?id=" + "&id=".join(lid for lid, _ in LISTINGS)


def parse_rsc(html):
    """Extract all RSC data from Next.js HTML."""
    next_f_chunks = re.findall(r'self\.__next_f\.push\(\[(.*?)\]\)', html, re.DOTALL)
    full_data = ""
    for chunk in next_f_chunks:
        try:
            parsed = json.loads(f"[{chunk}]")
            if len(parsed) >= 2 and isinstance(parsed[1], str):
                full_data += parsed[1]
        except:
            pass
    return full_data


def extract_json_array(data, key):
    """Find a JSON array after a given key string."""
    idx = data.find(key)
    if idx == -1:
        return None
    arr_start = data.find('[', idx + len(key))
    if arr_start == -1:
        return None
    depth = 0
    arr_end = arr_start
    for i, ch in enumerate(data[arr_start:arr_start + 200000]):
        if ch in '[{': depth += 1
        elif ch in ']}':
            depth -= 1
            if depth == 0:
                arr_end = arr_start + i + 1
                break
    try:
        return json.loads(data[arr_start:arr_end])
    except:
        return None


def extract_json_object(data, key):
    """Find a JSON object after a given key string."""
    idx = data.find(key)
    if idx == -1:
        return None
    obj_start = data.find('{', idx + len(key))
    if obj_start == -1:
        return None
    depth = 0
    obj_end = obj_start
    for i, ch in enumerate(data[obj_start:obj_start + 200000]):
        if ch in '[{': depth += 1
        elif ch in ']}':
            depth -= 1
            if depth == 0:
                obj_end = obj_start + i + 1
                break
    try:
        return json.loads(data[obj_start:obj_end])
    except:
        return None


def extract_string_value(data, key):
    """Extract a JSON string value after a key."""
    idx = data.find(key)
    if idx == -1:
        return None
    val_start = idx + len(key)
    # Skip whitespace and colon
    while val_start < len(data) and data[val_start] in ' \t\n\r:':
        val_start += 1
    if val_start >= len(data) or data[val_start] != '"':
        return None
    val_start += 1
    result = []
    i = val_start
    while i < len(data):
        ch = data[i]
        if ch == '\\' and i + 1 < len(data):
            nc = data[i+1]
            if nc == 'n': result.append('\n')
            elif nc == 't': result.append('\t')
            elif nc == 'r': result.append('\r')
            elif nc == '"': result.append('"')
            elif nc == '\\': result.append('\\')
            elif nc == 'u' and i + 5 < len(data):
                try:
                    result.append(chr(int(data[i+2:i+6], 16)))
                    i += 4
                except:
                    result.append('\\u')
            else:
                result.append(nc)
            i += 2
        elif ch == '"':
            break
        else:
            result.append(ch)
            i += 1
    return ''.join(result) if result else None


async def scrape_listing(page, lid, url):
    result = {"id": lid, "url": url}
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        result["http_status"] = resp.status if resp else 0

        if resp and resp.status >= 400:
            result["error"] = f"HTTP {resp.status}"
            return result

        await page.wait_for_timeout(4000)
        html = await page.evaluate("() => document.documentElement.outerHTML")
        result["html_length"] = len(html)

        page_title = await page.title()
        result["page_title"] = page_title

        if len(html) < 10000:
            result["error"] = f"Short page ({len(html)} bytes) — likely blocked"
            return result

        # Parse RSC
        rsc = parse_rsc(html)
        result["rsc_length"] = len(rsc)

        # --- Description ---
        for key in ['"description":', '"freeText":', '"freitext":', '"text":', '"descriptionText":']:
            val = extract_string_value(rsc, key)
            if val and len(val) > 30:
                result["description"] = val
                break

        # --- Features / Equipment ---
        for key in ['"features":', '"featureGroups":', '"equipment":', '"ausstattungList":',
                    '"highlights":', '"featureList":']:
            arr = extract_json_array(rsc, key)
            if arr and len(arr) > 0:
                result["features_raw"] = arr
                break

        # --- Full ad object ---
        ad_obj = extract_json_object(rsc, '"ad":')
        if ad_obj:
            result["ad"] = ad_obj

        # --- Details / specs dict ---
        for key in ['"details":', '"specs":', '"technicalDetails":']:
            obj = extract_json_object(rsc, key)
            if obj and len(obj) > 2:
                result["details"] = obj
                break

        # --- Fallback: full page text lines ---
        body_text = await page.locator("body").inner_text()
        lines = [l.strip() for l in body_text.split("\n") if l.strip() and len(l.strip()) > 1]
        result["page_lines"] = lines

    except Exception as e:
        result["error"] = str(e)

    return result


async def main():
    stealth = Stealth(
        navigator_languages_override=("de-DE", "de"),
        navigator_platform_override="iPhone",
    )

    from playwright.async_api import async_playwright
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

        # Warm up with park list for cookies
        print("Warming up with park list...")
        await page.goto(PARK_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(3000)
        print("Ready. Scraping listings...\n")

        results = []
        for i, (lid, url) in enumerate(LISTINGS):
            print(f"[{i+1}/{len(LISTINGS)}] {lid}...")
            data = await scrape_listing(page, lid, url)
            status = data.get("http_status", "?")
            html_len = data.get("html_length", 0)
            rsc_len = data.get("rsc_length", 0)
            desc_len = len(data.get("description") or "")
            feat_count = len(data.get("features_raw") or [])
            lines_count = len(data.get("page_lines") or [])
            err = data.get("error", "")
            print(f"  status={status} html={html_len} rsc={rsc_len} desc={desc_len} features={feat_count} lines={lines_count} {err}")
            results.append(data)
            if i < len(LISTINGS) - 1:
                await page.wait_for_timeout(2500)

        await browser.close()

    with open("/home/user/shit/listings3_detail.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(results)} results to listings3_detail.json")

asyncio.run(main())
