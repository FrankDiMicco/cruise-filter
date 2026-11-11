"""One-off: find the Princess pricing request variant that returns prices for every sailing."""
import json
from playwright.sync_api import sync_playwright

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
KEEP = ("accept", "appid", "bookingcompany", "content-type", "pcl-client-id", "productcompany", "reqsrc", "x-pcl-traceapp", "referer")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent=UA, viewport={"width": 1366, "height": 900}, locale="en-US", timezone_id="America/New_York")
    pg = ctx.new_page()
    cap = {}
    def on_req(r):
        if "pricing/v1/cruises" in r.url and "body" not in cap and r.method == "POST":
            cap.update(url=r.url, body=json.loads(r.post_data), headers={k: v for k, v in r.headers.items() if k in KEEP})
    pg.on("request", on_req)
    pg.goto("https://www.princess.com/cruise-search/results/", wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_function("() => { const s = window.__NEXT_REDUX_STORE__; return s && (s.getState().pricing.cruises.data || []).length > 0; }", timeout=90000)
    ids = pg.evaluate("() => window.__NEXT_REDUX_STORE__.getState().products.cruises.data.flatMap(p => (p.cruises || []).map(c => c.id))")
    print("DISC ids:", len(ids), ids[:5], "captured:", bool(cap), flush=True)

    def attempt(label, mutate):
        body = json.loads(json.dumps(cap["body"]))
        mutate(body)
        try:
            r = ctx.request.post(cap["url"], data=json.dumps(body), headers=cap["headers"], timeout=120000)
            t = r.text()
            try:
                j = json.loads(t)
                prods = j.get("products") or []
                n = sum(len(x.get("cruises") or []) for x in prods)
                metas = set()
                for x in prods[:40]:
                    for c in x.get("cruises") or []:
                        for f in (c.get("pricing") or {}).get("fares") or []:
                            for k in f.get("categories") or []:
                                metas.add(k.get("metaId") or (k.get("id") or "?")[0])
                print(f"DISC {label}: HTTP {r.status}, {len(t)} bytes, products {len(prods)}, cruises {n}, metas {sorted(metas)}", flush=True)
            except Exception:
                print(f"DISC {label}: HTTP {r.status}, {len(t)} bytes | {t[:300]}", flush=True)
        except Exception as e:
            print(f"DISC {label}: FAILED {type(e).__name__} {str(e)[:200]}", flush=True)

    attempt("as-is", lambda b: None)
    attempt("no leadInBy", lambda b: b.pop("leadInBy", None))
    attempt("leadInBy=cruises", lambda b: b.__setitem__("leadInBy", "cruises"))
    attempt("leadInBy=voyages", lambda b: b.__setitem__("leadInBy", "voyages"))
    attempt("100 ids + itins", lambda b: b["filters"].__setitem__("cruises", ids[:100]))
    def m(b):
        b["filters"]["cruises"] = ids[:100]; b.pop("leadInBy", None)
    attempt("100 ids, no leadInBy", m)
    def m2(b):
        b["filters"]["cruises"] = ids[:100]; b.pop("leadInBy", None); b["filters"].pop("meta", None)
    attempt("100 ids, no leadInBy, no meta", m2)
    def m3(b):
        b["filters"]["cruises"] = ids[:400]; b.pop("leadInBy", None)
    attempt("400 ids, no leadInBy", m3)
    b.close()
