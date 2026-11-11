"""One-off: list the URL parameters each cruise line's sailing page reads, to find one that preselects a cabin type."""
import json, re, urllib.request
from playwright.sync_api import sync_playwright
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
data = json.load(urllib.request.urlopen("https://frankdimicco.github.io/cruise-filter/sailings.json"))
pick = {}
for r in data["sailings"]:
    if r["line"] not in pick and r["start_date"] > "2027-03-01" and r.get("price_interior") and r.get("price_suite") and r.get("price_balcony"):
        pick[r["line"]] = r
pick.setdefault("Virgin Voyages", next(r for r in data["sailings"] if r["line"] == "Virgin Voyages" and r["start_date"] > "2027-03-01"))
PAT = [r'searchParams\.(?:get|set|append|has)\(\s*["\']([\w.-]{2,40})["\']', r'\.get\(\s*["\']([\w.-]{2,40})["\']\s*\)', r'[?&]([A-Za-z][\w]{2,30})=\$\{', r'[?&]([A-Za-z][\w]{2,30})=["\']\s*\+', r'query\.([A-Za-z]\w{2,30})\b']
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent=UA, viewport={"width": 1366, "height": 900}, locale="en-US", timezone_id="America/New_York")
    for line, r in pick.items():
        try:
            pg = ctx.new_page()
            pg.goto(r["url"], wait_until="domcontentloaded", timeout=90000)
            pg.wait_for_timeout(12000)
            print(f"DISC {line} | url {pg.url[:230]}", flush=True)
            print(f"DISC {line} | prices I={r.get('price_interior')} O={r.get('price_outside')} B={r.get('price_balcony')} S={r.get('price_suite')}", flush=True)
            srcs = pg.evaluate("() => [...new Set([...document.scripts].map(s => s.src).filter(Boolean).concat(performance.getEntriesByType('resource').map(e => e.name).filter(n => /\\.js(\\?|$)/.test(n))))]")
            host = re.sub(r"^https://(www\.)?", "", r["url"]).split("/")[0].split(".")[-2]
            names = {}
            for u in srcs:
                if host not in u: continue
                try: t = ctx.request.get(u, timeout=30000).text()
                except Exception: continue
                for pat in PAT:
                    for m in re.finditer(pat, t):
                        names[m.group(1)] = names.get(m.group(1), 0) + 1
            keep = sorted(n for n in names if re.search(r"room|cabin|categ|meta|class|type|suite|berth|fare|price|sail|voyage|package|guest|pax|adult", n, re.I))
            print(f"DISC {line} | params {keep[:120]}", flush=True)
            hrefs = pg.evaluate("() => [...new Set([...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href')).filter(h => /book|room|cabin|stateroom|categ|checkout/i.test(h)))].slice(0, 8)")
            print(f"DISC {line} | hrefs {[h[:260] for h in hrefs]}", flush=True)
            pg.close()
        except Exception as e:
            print(f"DISC {line} | FAILED {type(e).__name__} {str(e)[:200]}", flush=True)
    b.close()
