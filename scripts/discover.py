"""One-off: see whether a headless browser on this machine can reach MSC and Princess, and log how Princess asks for prices."""
import json, sys
from playwright.sync_api import sync_playwright

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
MSC_JS = """async () => { try { const r = await fetch('/api-search/1/indexes/*/queries', {method:'POST', headers:{accept:'application/json','Content-Type':'application/json','MSC-Locale':'en_US'}, body: JSON.stringify({requests:[{indexName:'prod-en-us-itinerary-deduplication-relevance', distinct:0, filters:'(noofAdults=2) AND (hasAir: false)', hitsPerPage:1, page:0}]})}); const t = await r.text(); return {status:r.status, head:t.slice(0,200)}; } catch (e) { return {err:String(e)}; } }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent=UA, viewport={"width": 1366, "height": 900}, locale="en-US", timezone_id="America/New_York")
    ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # ---- MSC ----
    try:
        pg = ctx.new_page()
        resp = pg.goto("https://www.msccruisesusa.com/search", wait_until="domcontentloaded", timeout=90000)
        pg.wait_for_timeout(9000)
        print("DISC MSC page:", resp.status if resp else None, "|", pg.title()[:80], flush=True)
        print("DISC MSC api:", json.dumps(pg.evaluate(MSC_JS))[:400], flush=True)
        pg.close()
    except Exception as e:
        print("DISC MSC FAILED:", type(e).__name__, str(e)[:300], flush=True)

    # ---- Princess ----
    try:
        pg = ctx.new_page()
        seen = []
        def on_req(r):
            if "pricing/v1/cruises" in r.url and len(seen) < 3:
                seen.append(r)
                body = r.post_data or ""
                print("DISC PCL req:", r.method, r.url, "| header names:", sorted(r.headers.keys()), flush=True)
                print("DISC PCL body len:", len(body), flush=True)
                for i in range(0, min(len(body), 6000), 1500):
                    print("DISC PCL body:", body[i:i + 1500], flush=True)
        def on_resp(r):
            if "pricing/v1/cruises" in r.url:
                try:
                    t = r.text()
                    print("DISC PCL resp:", r.status, len(t), "|", t[:300], flush=True)
                except Exception as e:
                    print("DISC PCL resp err:", e, flush=True)
        pg.on("request", on_req)
        pg.on("response", on_resp)
        resp = pg.goto("https://www.princess.com/cruise-search/results/", wait_until="domcontentloaded", timeout=90000)
        pg.wait_for_timeout(20000)
        print("DISC PCL page:", resp.status if resp else None, "|", pg.title()[:80], flush=True)
        info = pg.evaluate("""() => { const s = window.__NEXT_REDUX_STORE__; if (!s) return {store:false}; const st = s.getState(); const pr = (st.pricing.cruises.data || []); return {store:true, products:(st.products.cruises.data || []).length, pricing: pr.length, pricedCruises: pr.reduce((n, p) => n + (p.cruises || []).length, 0), settings: JSON.stringify(st.admin.data.ube.settings).slice(0, 600)}; }""")
        print("DISC PCL store:", json.dumps(info)[:900], flush=True)
        pg.close()
    except Exception as e:
        print("DISC PCL FAILED:", type(e).__name__, str(e)[:300], flush=True)
    b.close()
