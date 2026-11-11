"""Pulls for lines whose data only loads inside a real browser (MSC, Princess).

Each one opens the cruise line's own search page in headless Chromium and makes
the same requests that page makes, from inside the page.
"""
import json, time, urllib.parse
from datetime import date, timedelta

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

MSC_JS = r"""
async () => {
  const ships = await (async () => {
    const r = await fetch('/api-search/1/indexes/*/queries', {method:'POST', headers:{accept:'application/json','Content-Type':'application/json','MSC-Locale':'en_US'},
      body: JSON.stringify({requests:[{indexName:'prod-en-us-itinerary-deduplication-relevance', distinct:0, filters:'(noofAdults=2) AND (hasAir: false)', hitsPerPage:0, page:0, facets:['shipCd.key']}]})});
    if (!r.ok) throw new Error('facet HTTP ' + r.status);
    return Object.keys((await r.json()).results[0].facets['shipCd.key']);
  })();
  const slices = [];
  for (const s of ships) {
    for (const c of ['INS','OUT','SUI','YTC']) slices.push('shipCd.key:"' + s + '" AND macroCategory.key:' + c);
    slices.push('shipCd.key:"' + s + '" AND macroCategory.key:BAL AND priceType:"EZAT"');
    slices.push('shipCd.key:"' + s + '" AND macroCategory.key:BAL AND NOT priceType:"EZAT"');
  }
  const cruises = {}, failed = [], capped = [];
  const q = async (filt, page) => {
    const r = await fetch('/api-search/1/indexes/*/queries', {method:'POST', headers:{accept:'application/json','Content-Type':'application/json','MSC-Locale':'en_US'},
      body: JSON.stringify({requests:[{indexName:'prod-en-us-itinerary-deduplication-relevance', distinct:0,
        filters: filt + ' AND (noofAdults=2) AND (noofMinors=0) AND (noofJuniors=0) AND (prices.availability:true) AND NOT priceType:"EZBR" AND (hasAir: false)',
        hitsPerPage:1000, page, attributesToRetrieve:['cruiseID','departureStartDate','embkPort','shipCd','itineraryName','numberOfNights','portOfCalls','visitingPorts','macroCategory','prices.adultPrice','itinCd'], attributesToHighlight:['']}]})});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return (await r.json()).results[0];
  };
  let i = 0;
  const worker = async () => {
    while (i < slices.length) {
      const f = slices[i++];
      try {
        let page = 0, nb = 1;
        while (page < nb) {
          const res = await q(f, page); nb = res.nbPages;
          if (page === 0 && res.nbHits > 8000) capped.push(f);
          for (const h of res.hits) {
            const o = cruises[h.cruiseID] || (cruises[h.cruiseID] = {id:h.cruiseID, itin:h.itinCd, ship:h.shipCd && h.shipCd.value, name:h.itineraryName, nights:h.numberOfNights,
              depart:h.embkPort && h.embkPort.value, start:h.departureStartDate, ports:(h.visitingPorts || []).map(p => p.value), sea:(h.portOfCalls || []).filter(c => c === 'SEADAY').length, cab:{}});
            const p = h.prices && h.prices.adultPrice, k = h.macroCategory.key;
            if (p > 0) o.cab[k] = Math.min(o.cab[k] || 1e9, p);
          }
          page++; await new Promise(z => setTimeout(z, 300));
        }
      } catch (e) { failed.push(f + ': ' + e); }
    }
  };
  await Promise.all([worker(), worker()]);
  return {cruises: Object.values(cruises), failed, capped};
}
"""

PRINCESS_JS = r"""
async ({url, headers, body}) => {
  const st = window.__NEXT_REDUX_STORE__.getState();
  const ports = Object.fromEntries(st.ports.data.map(p => [p.id, p.name]));
  const ships = Object.fromEntries(st.ships.data.map(s => [s.id, s.name]));
  const sailings = [];
  for (const p of st.products.cruises.data) for (const c of p.cruises || []) {
    const v = c.voyage || {};
    sailings.push({id:c.id, name:p.name, nights:v.duration || p.cruiseDuration, ship:ships[v.ship && v.ship.id] || (v.ship && v.ship.id),
      depart:ports[v.startPortId] || v.startPortId, ports:(v.ports || []).map(i => ports[i] || i), start:c.startDate, end:c.endDate});
  }
  const ids = [...new Set(sailings.map(s => s.id))], price = {}, errors = [], currency = {};
  const base = JSON.parse(body);
  for (let i = 0; i < ids.length; i += 100) {
    try {
      base.filters.cruises = ids.slice(i, i + 100);
      const r = await fetch(url, {method:'POST', headers, body: JSON.stringify(base)});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      for (const p of (await r.json()).products || []) for (const c of p.cruises || []) {
        const cab = {};
        if (c.pricing && c.pricing.fareCurrency) currency[c.pricing.fareCurrency] = 1;
        for (const f of (c.pricing && c.pricing.fares) || []) for (const k of f.categories || []) {
          const m = k.metaId || (k.id || '')[0];
          if (k.averageGuestPrice > 0 && k.status !== 'N' && m) cab[m] = Math.min(cab[m] || 1e9, k.averageGuestPrice);
        }
        price[c.id] = cab;
      }
    } catch (e) { errors.push(i + ': ' + e); }
    await new Promise(z => setTimeout(z, 300));
  }
  return {sailings, price, errors, currency: Object.keys(currency)};
}
"""


def _browser(p):
    b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent=UA, locale="en-US", timezone_id="America/New_York", viewport={"width": 1366, "height": 900})
    return b, ctx.new_page()


def pull_msc(row):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b, page = _browser(p)
        try:
            page.goto("https://www.msccruisesusa.com/search", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(8000)
            data = page.evaluate(MSC_JS)
        finally:
            b.close()
    if data["failed"] or data["capped"]:
        raise RuntimeError(f"{len(data['failed'])} failed and {len(data['capped'])} capped slices: {(data['failed'] + data['capped'])[:2]}")
    rows = []
    for c in data["cruises"]:
        cab = c["cab"]
        suite = [x for x in (cab.get("SUI"), cab.get("YTC")) if x]
        start = date.fromisoformat(c["start"])
        ports = []
        for n in c["ports"]:
            if n and n != c["depart"] and n not in ports:
                ports.append(n)
        url = ("https://www.msccruisesusa.com/search/itinerary?cruiseId=" + urllib.parse.quote(c["id"])
               + "&itineraryCode=" + urllib.parse.quote(c["itin"]) + "&viewPrice=person")
        rows.append(row("MSC", c["ship"], c["name"], c["nights"], c["depart"], c["start"], (start + timedelta(days=c["nights"])).isoformat(),
                        ports, c["sea"], {"interior": cab.get("INS"), "outside": cab.get("OUT"), "balcony": cab.get("BAL"),
                                          "suite": min(suite) if suite else None}, url))
    return rows


def pull_princess(row):
    from playwright.sync_api import sync_playwright
    seen = {}

    def on_request(req):
        if "/pricing/v1/cruises" in req.url and req.method == "POST" and not seen:
            seen.update(url=req.url, headers=req.all_headers(), body=req.post_data)

    with sync_playwright() as p:
        b, page = _browser(p)
        try:
            page.on("request", on_request)
            page.goto("https://www.princess.com/cruise-search/results/", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_function(
                "() => { try { const s = window.__NEXT_REDUX_STORE__.getState(); return s.products.cruises.data.length > 100 && s.pricing.cruises.data.length > 100 && s.ports.data.length > 50; } catch (e) { return false; } }",
                timeout=120000)
            for _ in range(20):
                if seen:
                    break
                page.wait_for_timeout(500)
            if not seen:
                raise RuntimeError("the page never made its pricing request")
            keep = ("accept", "content-type", "appid", "productcompany", "bookingcompany", "reqsrc", "pcl-client-id", "x-pcl-traceapp")
            headers = {k: v for k, v in seen["headers"].items() if k.lower() in keep}
            data = page.evaluate(PRINCESS_JS, {"url": seen["url"], "headers": headers, "body": seen["body"]})
        finally:
            b.close()
    if data["errors"]:
        raise RuntimeError(f"{len(data['errors'])} pricing requests failed: {data['errors'][:2]}")
    if data["currency"] != ["USD"]:
        raise RuntimeError(f"prices came back in {data['currency']}, expected USD only")
    iso = lambda s: f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    rows = []
    for s in data["sailings"]:
        cab = data["price"].get(s["id"]) or {}
        ports = []
        for n in s["ports"]:
            if n and n != s["depart"] and n not in ports:
                ports.append(n)
        url = "https://www.princess.com/cruise-search/details/?voyageCode=" + urllib.parse.quote(s["id"])
        rows.append(row("Princess", s["ship"], f"{s['nights']}-Day {s['name']}", s["nights"], s["depart"], iso(s["start"]), iso(s["end"]), ports, None,
                        {"interior": cab.get("I"), "outside": cab.get("O"), "balcony": cab.get("B"), "suite": cab.get("S") or cab.get("M")}, url))
    return rows
