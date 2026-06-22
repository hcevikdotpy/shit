import asyncio
import json
import re
from playwright_stealth import Stealth

PARK_URL = "https://www.mobile.de/park/list?id=440029792&id=457551621&id=456333942&id=457717885&id=458711959&id=458501356&id=457988469&id=414721913&id=457434243&id=457257293&id=457229728&id=442782174&id=454899106&id=452510888"

LISTINGS = [
    ("440029792", "renault-captur-luxe-1-2-aut-navi-r-cam-szh-8xlmf-temp-hu-zwickau"),
    ("457551621", "mercedes-benz-c-180-c-coupe-c-180-cgi-blueefficiency-t%C3%BCv-neu-krostitz"),
    ("456333942", "hyundai-i20-1-4-style-aut-klima-pdc-freispr-alus-t%C3%BCv-neu-berlin"),
    ("457717885", "bmw-116-1-limousine-automatik-schiebedach-leder-berlin"),
    ("458711959", "audi-a5-sportback-1-8-tfsi-bi-xenon-aac-pdc-shz-19z-brehna"),
    ("458501356", "audi-a3-1-8-tfsi-sportback-aut-steuerkette-neu-1hand-berlin"),
    ("457988469", "bmw-118i-f20-sport-line-led-automatik-wenig-km-berlin"),
    ("414721913", "bmw-116-i-lim-5-trg-automatik-pdc-klima-berlin"),
    ("457434243", "bmw-320-i-limousine-navi-bixenon-leder-pdc-tempomat-berlin"),
    ("457257293", "bmw-116-i-automatik-pdc-2-hand-allwetter-nauen"),
    ("457229728", "bmw-118-i-limousine-urban-autom-xen-klima-pdc-shz-sch%C3%B6nefeld-ot-gro%C3%9Fziethen"),
    ("442782174", "audi-a3-quattro-lim-berlin"),
    ("454899106", "kia-rio-spirit-automatik-kamera-tempomat-sitzheizung-sch%C3%B6neiche-bei-berlin"),
    ("452510888", "bmw-116-116-i-xenon-automatik-ahk-2-hand-brandenburg"),
]

captured_rsc = {}

def parse_rsc_for_details(rsc_data):
    """Extract description and features from RSC data."""
    result = {}

    def extract_string(data, key):
        idx = data.find(key)
        if idx == -1:
            return None
        val_start = idx + len(key)
        while val_start < len(data) and data[val_start] in ' \t\n\r':
            val_start += 1
        if val_start >= len(data) or data[val_start] != '"':
            return None
        val_start += 1
        chars = []
        i = val_start
        while i < len(data):
            ch = data[i]
            if ch == '\\' and i+1 < len(data):
                nc = data[i+1]
                if nc == 'n': chars.append('\n')
                elif nc == 't': chars.append('\t')
                elif nc == '"': chars.append('"')
                elif nc == '\\': chars.append('\\')
                elif nc == 'u' and i+5 < len(data):
                    try: chars.append(chr(int(data[i+2:i+6], 16))); i += 4
                    except: pass
                else: chars.append(nc)
                i += 2
            elif ch == '"':
                break
            else:
                chars.append(ch); i += 1
        return ''.join(chars) if chars else None

    def extract_array(data, key):
        idx = data.find(key)
        if idx == -1:
            return None
        arr_start = data.find('[', idx + len(key))
        if arr_start == -1:
            return None
        depth = 0
        for i, ch in enumerate(data[arr_start:arr_start+300000]):
            if ch in '[{': depth += 1
            elif ch in ']}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(data[arr_start:arr_start+i+1])
                    except:
                        return None
        return None

    def extract_object(data, key):
        idx = data.find(key)
        if idx == -1:
            return None
        obj_start = data.find('{', idx + len(key))
        if obj_start == -1:
            return None
        depth = 0
        for i, ch in enumerate(data[obj_start:obj_start+300000]):
            if ch in '[{': depth += 1
            elif ch in ']}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(data[obj_start:obj_start+i+1])
                    except:
                        return None
        return None

    # Description
    for key in ['"description":', '"freeText":', '"freitext":', '"descriptionText":',
                '"text":', '"sellerNote":', '"notes":']:
        val = extract_string(rsc_data, key)
        if val and len(val) > 40:
            result['description'] = val
            break

    # Features
    for key in ['"features":', '"featureGroups":', '"equipment":', '"highlights":',
                '"featureList":', '"ausstattung":', '"equipmentList":']:
        arr = extract_array(rsc_data, key)
        if arr and len(arr) > 0:
            result['features'] = arr
            break

    # Vehicle details object
    for key in ['"vehicleData":', '"vehicle":', '"listing":', '"ad":']:
        obj = extract_object(rsc_data, key)
        if obj and len(obj) > 5:
            result['vehicle_obj'] = obj
            break

    return result


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

        # Intercept RSC responses
        async def on_response(resp):
            url = resp.url
            ct = resp.headers.get('content-type', '')
            if ('mobile.de' in url and 'auto-inserat' in url) or 'text/x-component' in ct:
                try:
                    body = await resp.body()
                    decoded = body.decode('utf-8', errors='replace')
                    for lid, _ in LISTINGS:
                        if lid in url:
                            captured_rsc[lid] = captured_rsc.get(lid, "") + decoded
                            break
                    else:
                        if 'auto-inserat' in url:
                            captured_rsc[f"unknown_{url[-20:]}"] = decoded
                    print(f"  CAPTURED: {url[-60:]} [{len(decoded)} bytes] ct={ct[:30]}")
                except:
                    pass

        # Try method 1: m.mobile.de/goto/ links
        page = await context.new_page()
        page.on("response", on_response)

        print("Loading park list...")
        await page.goto(PARK_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(3000)

        print("\nTrying m.mobile.de/goto/ for first 3 vehicles...")
        for lid, slug in LISTINGS[:3]:
            goto_url = f"https://m.mobile.de/goto/fahrzeuge/details.html?id={lid}&scopeId=C&action=parkItem&vc=Car&s=Car"
            print(f"\nNavigating to goto URL for {lid}...")
            try:
                resp = await page.goto(goto_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(3000)
                print(f"  Status: {resp.status}, URL: {page.url}")
                title = await page.title()
                print(f"  Title: {title}")
                html = await page.evaluate("() => document.documentElement.outerHTML")
                print(f"  HTML: {len(html)} bytes")
                if len(html) > 50000:
                    rsc = ""
                    chunks = re.findall(r'self\.__next_f\.push\(\[(.*?)\]\)', html, re.DOTALL)
                    for chunk in chunks:
                        try:
                            parsed = json.loads(f"[{chunk}]")
                            if len(parsed) >= 2 and isinstance(parsed[1], str):
                                rsc += parsed[1]
                        except:
                            pass
                    print(f"  RSC: {len(rsc)} bytes")
                    details = parse_rsc_for_details(rsc)
                    print(f"  Description: {(details.get('description','')[:100])}")
                    print(f"  Features: {len(details.get('features') or [])} items")
                    captured_rsc[lid] = rsc
                    # Go back to park list for next iteration
                    await page.go_back()
                    await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"  Error: {e}")

        await browser.close()

    print(f"\n=== Captured RSC for {len(captured_rsc)} listings ===")
    for lid, rsc in captured_rsc.items():
        print(f"  {lid}: {len(rsc)} bytes")

asyncio.run(main())
