import asyncio
import json
import re
from playwright_stealth import Stealth

PARK_URL = "https://www.mobile.de/park/list?id=440029792&id=457551621&id=456333942&id=457717885&id=458711959&id=458501356&id=457988469&id=414721913&id=457434243&id=457257293&id=457229728&id=442782174&id=454899106&id=452510888"

LISTING_IDS = [
    "440029792", "457551621", "456333942", "457717885", "458711959",
    "458501356", "457988469", "414721913", "457434243", "457257293",
    "457229728", "442782174", "454899106", "452510888",
]

def parse_rsc(html_or_rsc, is_rsc=False):
    if is_rsc:
        return html_or_rsc
    next_f_chunks = re.findall(r'self\.__next_f\.push\(\[(.*?)\]\)', html_or_rsc, re.DOTALL)
    full = ""
    for chunk in next_f_chunks:
        try:
            parsed = json.loads(f"[{chunk}]")
            if len(parsed) >= 2 and isinstance(parsed[1], str):
                full += parsed[1]
        except:
            pass
    return full

def extract_description(rsc):
    for key in ['"description":', '"freeText":', '"freitext":', '"descriptionText":',
                '"sellerNote":', '"text":']:
        idx = rsc.find(key)
        if idx == -1:
            continue
        val_start = rsc.find('"', idx + len(key))
        if val_start == -1:
            continue
        val_start += 1
        chars = []
        i = val_start
        while i < len(rsc):
            ch = rsc[i]
            if ch == '\\' and i+1 < len(rsc):
                nc = rsc[i+1]
                if nc == 'n': chars.append('\n')
                elif nc == 't': chars.append('\t')
                elif nc == '"': chars.append('"')
                elif nc == '\\': chars.append('\\')
                elif nc == 'u' and i+5 < len(rsc):
                    try: chars.append(chr(int(rsc[i+2:i+6], 16))); i += 4
                    except: pass
                else: chars.append(nc)
                i += 2
            elif ch == '"':
                break
            else:
                chars.append(ch); i += 1
        val = ''.join(chars)
        if len(val) > 40:
            return val
    return None

def extract_features(rsc):
    for key in ['"features":', '"featureGroups":', '"equipment":', '"highlights":',
                '"featureList":', '"ausstattung":']:
        idx = rsc.find(key)
        if idx == -1:
            continue
        arr_start = rsc.find('[', idx + len(key))
        if arr_start == -1:
            continue
        depth = 0
        for i, ch in enumerate(rsc[arr_start:arr_start+500000]):
            if ch in '[{': depth += 1
            elif ch in ']}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(rsc[arr_start:arr_start+i+1])
                    except:
                        break
    return None


async def main():
    from playwright.async_api import async_playwright

    stealth = Stealth(navigator_languages_override=("de-DE","de"), navigator_platform_override="iPhone")
    rsc_captures = {}  # lid -> rsc text

    async with stealth.use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/21A329 mobile.de/8.2",
            viewport={"width": 390, "height": 844},
            locale="de-DE",
            is_mobile=True,
        )

        async def on_response(resp):
            url = resp.url
            ct = resp.headers.get('content-type', '')
            status = resp.status
            if status == 200 and ('mobile.de' in url):
                is_rsc = 'text/x-component' in ct or '_rsc=' in url
                is_html = 'text/html' in ct and 'auto-inserat' in url
                if is_rsc or is_html:
                    try:
                        body = await resp.body()
                        decoded = body.decode('utf-8', errors='replace')
                        for lid in LISTING_IDS:
                            if lid in url:
                                existing = rsc_captures.get(lid, "")
                                rsc_captures[lid] = existing + decoded
                                print(f"    RSC/HTML: {url[-70:]} [{len(decoded)}b] ct={ct[:20]}")
                                break
                    except:
                        pass

        page = await context.new_page()
        page.on("response", on_response)

        print("Loading park list...")
        await page.goto(PARK_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(4000)

        # Find all listing card links
        links = await page.evaluate("""() => {
            const anchors = Array.from(document.querySelectorAll('a[href*="auto-inserat"], a[href*="fahrzeuge"]'));
            return anchors.map(a => ({ href: a.href, text: a.textContent.trim().substring(0,50) }));
        }""")
        print(f"\nFound {len(links)} listing links in page")
        for l in links[:5]:
            print(f"  {l}")

        # Try clicking each vehicle card directly
        print("\nAttempting to trigger Next.js navigation for each listing...")

        # Try programmatic Next.js router navigation
        for lid in LISTING_IDS:
            slug_url = await page.evaluate(f"""() => {{
                const links = Array.from(document.querySelectorAll('a[href*="{lid}"]'));
                return links.map(l => l.href).join(' | ');
            }}""")

            if slug_url:
                print(f"\n[{lid}] Found link: {slug_url[:100]}")

                # Try to extract the href and use JS to trigger the navigation  
                actual_href = await page.evaluate(f"""() => {{
                    const link = document.querySelector('a[href*="{lid}"]');
                    return link ? link.getAttribute('href') : null;
                }}""")

                if actual_href:
                    print(f"  href: {actual_href}")
                    # Use Next.js router to navigate
                    nav_result = await page.evaluate(f"""async () => {{
                        try {{
                            // Try to use Next.js router
                            const nextData = window.__NEXT_DATA__;
                            // Try window.next if available
                            if (window.next && window.next.router) {{
                                window.next.router.push('{actual_href}');
                                return {{ method: 'next.router' }};
                            }}
                            return {{ method: 'none', nextData: !!nextData }};
                        }} catch(e) {{
                            return {{ error: e.message }};
                        }}
                    }}""")
                    print(f"  nav_result: {nav_result}")
                    await page.wait_for_timeout(2000)
            else:
                print(f"\n[{lid}] No link found in page DOM")

        await page.wait_for_timeout(3000)
        await browser.close()

    print(f"\n=== Results ===")
    for lid, rsc in rsc_captures.items():
        desc = extract_description(rsc) or ""
        feats = extract_features(rsc) or []
        print(f"{lid}: {len(rsc)} bytes rsc | desc: {len(desc)} chars | features: {len(feats)}")

asyncio.run(main())
