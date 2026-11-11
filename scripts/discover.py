"""One-off: test candidate link parameters that might preselect a cabin type, and print script snippets that mention them."""
import json, re, urllib.request
from playwright.sync_api import sync_playwright
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
data = json.load(urllib.request.urlopen("https://frankdimicco.github.io/cruise-filter/sailings.json"))
pick = {}
for r in data["sailings"]:
    if r["line"] not in pick and r["start_date"] > "2027-03-01" and r.get("price_interior") and r.get("price_suite") and r.get("price_balcony"):
        pick[r["line"]] = r
pick.setdefault("Virgin Voyages", next(r for r in data["sailings"] if r["line"] == "Virgin Voyages" and r["start_date"] > "2027-03-01"))
TESTS = {
    "Royal Caribbean": ["&cabinClassType=DELUXE", "&stateroomClass=DELUXE", "&roomType=DELUXE"],
    "Celebrity": ["&cabinClassType=DELUXE"],
    "Norwegian": ["&stateroomTypeCode=BALCONY", "&stateroomTypeCode=SUITE"],
    "MSC": ["&macroCategory=SUI", "&cabinType=SUI"],
    "Princess": ["&meta=B", "&meta=S"],
    "Virgin Voyages": ["&type=SEA%20TERRACE", "&metaCode=SEA%20TERRACE"],
}
KEYS = {
    "Royal Caribbean": ["cabinClassType", "room-selection", "roomType=", "stateroomClass="],
    "Celebrity": [],
    "Norwegian": ["stateroomTypeCode"],
    "MSC": ["macroCategory=", "cabinType=", "cabin-section", "selectedCabin", "categoryCode="],
    "Princess": ['get("meta")', "meta=", "stateRoomId"],
    "Virgin Voyages": ["chosenSubCategoryCode", "fareClass", "cabinType=", "metaCode"],
}
def look(pg, label):
    pg.wait_for_timeout(12000)
    txt = pg.evaluate("() => { const out = []; const walk = (root) => { for (const el of root.querySelectorAll('*')) if (el.shadowRoot) walk(el.shadowRoot); const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n; while ((n = tw.nextNode())) { const t = n.textContent.trim(); if (t && t.length < 80) out.push(t); } }; walk(document); return out.join(' | '); }")
    amts = re.findall(r"\$\s?[\d,]{3,}(?:\.\d\d)?", txt)[:14]
    hint = [m.group(0)[:90] for m in re.finditer(r"[^|]{0,40}(Suite|Balcony|Interior|Inside|Ocean ?view|Sea Terrace|room type|Stateroom)[^|]{0,40}", txt)][:8]
    print(f"DISC {label} | final {pg.url[:210]} | amounts {amts} | hints {hint}", flush=True)
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent=UA, viewport={"width": 1366, "height": 900}, locale="en-US", timezone_id="America/New_York")
    for line, r in pick.items():
        print(f"DISC {line} | prices I={r.get('price_interior')} O={r.get('price_outside')} B={r.get('price_balcony')} S={r.get('price_suite')} | {r['url'][:200]}", flush=True)
        try:
            pg = ctx.new_page(); pg.goto(r["url"], wait_until="domcontentloaded", timeout=90000); look(pg, line + " base")
            if KEYS[line]:
                srcs = pg.evaluate("() => [...new Set([...document.scripts].map(s => s.src).filter(Boolean).concat(performance.getEntriesByType('resource').map(e => e.name).filter(n => /\\.js(\\?|$)/.test(n))))]")
                seen = set()
                for u in srcs:
                    if re.search(r"google|facebook|tiktok|adobe|doubleclick|bing|tiqcdn|contentsquare|dynatrace|onetrust|qualtrics|newrelic", u): continue
                    try: t = ctx.request.get(u, timeout=30000).text()
                    except Exception: continue
                    for k in KEYS[line]:
                        for m in list(re.finditer(re.escape(k), t))[:3]:
                            s = re.sub(r"\s+", " ", t[max(0, m.start() - 170):m.end() + 230])
                            if s[:60] not in seen and len(seen) < 9:
                                seen.add(s[:60]); print(f"DISC {line} | js[{k}] {s}", flush=True)
            pg.close()
            for extra in TESTS[line]:
                pg = ctx.new_page(); pg.goto(r["url"] + extra, wait_until="domcontentloaded", timeout=90000); look(pg, line + " " + extra); pg.close()
        except Exception as e:
            print(f"DISC {line} | FAILED {type(e).__name__} {str(e)[:200]}", flush=True)
    b.close()
