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

        print("Loading park list for session...")
        await page.goto(PARK_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(3000)
        print("Session established.\n")

        # Try multiple approaches for each listing
        for lid, url in LISTINGS[:2]:
            print(f"\n=== {lid} ===")

            # Approach 1: RSC header
            result1 = await page.evaluate(f"""async () => {{
                const r = await fetch('{url}', {{
                    credentials: 'include',
                    headers: {{
                        'RSC': '1',
                        'Next-Router-State-Tree': '%5B%22%22%2C%7B%7D%5D',
                        'accept': 'text/x-component',
                        'accept-language': 'de-DE,de;q=0.9',
                    }}
                }}).catch(e => ({{ error: e.message }}));
                if (r.error) return r;
                const text = await r.text();
                return {{ status: r.status, ct: r.headers.get('content-type'), length: text.length, snippet: text.substring(0, 400) }};
            }}""")
            print(f"RSC header: status={result1.get('status')} len={result1.get('length')} ct={result1.get('ct')}")
            if result1.get('snippet'):
                print(f"  {result1['snippet'][:200]}")

            # Approach 2: Next-Router-Prefetch
            result2 = await page.evaluate(f"""async () => {{
                const r = await fetch('{url}', {{
                    credentials: 'include',
                    headers: {{
                        'Next-Router-Prefetch': '1',
                        'RSC': '1',
                        'accept': 'text/x-component',
                        'accept-language': 'de-DE,de;q=0.9',
                        'sec-fetch-dest': 'empty',
                        'sec-fetch-mode': 'cors',
                        'sec-fetch-site': 'same-origin',
                    }}
                }}).catch(e => ({{ error: e.message }}));
                if (r.error) return r;
                const text = await r.text();
                return {{ status: r.status, ct: r.headers.get('content-type'), length: text.length, snippet: text.substring(0, 400) }};
            }}""")
            print(f"RSC prefetch: status={result2.get('status')} len={result2.get('length')} ct={result2.get('ct')}")
            if result2.get('snippet'):
                print(f"  {result2['snippet'][:200]}")

        await browser.close()

asyncio.run(main())
