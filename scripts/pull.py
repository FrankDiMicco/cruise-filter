#!/usr/bin/env python3
"""Daily data pull for Cruise Filter.

Pulls Royal Caribbean, Celebrity, Norwegian and Virgin Voyages over plain HTTP,
and MSC and Princess through a headless browser (scripts/browser_lines.py).
Carries forward any line that could not be pulled from the previous data file,
tags regions, tracks price changes, and writes sailings.json + history.json.

    python3 scripts/pull.py --prev site/sailings.json --history site/history.json --out out
"""
import argparse, hashlib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regions

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
TZ = ZoneInfo("America/New_York")


def http(url, body=None, headers=None, tries=3):
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    if body is not None:
        body = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=h, method="POST" if body else "GET")
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # retry on anything, then give up
            last = e
            time.sleep(3 * (attempt + 1))
    raise last


def port(s):
    if not s:
        return s
    if "Canaveral" in s:
        return "Port Canaveral"
    return s.split(",")[0].strip().replace("Ft. ", "Fort ")


def money(v):
    return v if isinstance(v, (int, float)) and v > 0 else None


def row(line, ship, itinerary, nights, depart, start, end, ports, sea, cab, url):
    """cab: dict with interior/outside/balcony/suite prices (per person)."""
    four = [cab.get(k) for k in ("interior", "outside", "balcony", "suite") if cab.get(k)]
    return {
        "line": line, "ship": ship, "itinerary": itinerary, "nights": nights, "departure_port": port(depart),
        "start_date": start, "end_date": end,
        "ports": [p for p in ports if p.lower() not in ("day at sea", "at sea", "cruising")],
        "sea_days": sea, "price_from": min(four) if four else None,
        "price_interior": cab.get("interior"), "price_outside": cab.get("outside"),
        "price_balcony": cab.get("balcony"), "price_suite": cab.get("suite"), "url": url,
    }


# ---------- Royal Caribbean / Celebrity ----------
RC_QUERY = """query CruiseSearch($filters: String, $sort: CruiseSearchSort, $pagination: CruiseSearchPagination) {
 cruiseSearch(filters: $filters, sort: $sort, pagination: $pagination) { results { total cruises { id productViewLink
  masterSailing { itinerary { name code sailingNights totalNights departurePort { name } ship { code name } days { number ports { port { name } } } } }
  sailings { itinerary { name code sailingNights totalNights departurePort { name } ship { code name } days { number ports { port { name } } } }
   startDate endDate stateroomClassPricing { price { value } stateroomClass { id } } } } } } }"""


def merged(a, b):
    out = dict(a or {})
    out.update({k: v for k, v in (b or {}).items() if v is not None})
    return out


def pull_royal(line, site, brand=None):
    headers = {"brand": brand} if brand else {}
    groups, total = [], None
    while total is None or len(groups) < total:
        data = json.loads(http(site + "/cruises/graph", {
            "operationName": "CruiseSearch", "query": RC_QUERY,
            "variables": {"filters": None, "sort": {"by": "RECOMMENDED"}, "pagination": {"count": 50, "skip": len(groups)}}}, headers))
        if data.get("errors"):
            raise RuntimeError(str(data["errors"])[:300])
        res = data["data"]["cruiseSearch"]["results"]
        total = res["total"]
        if not res.get("cruises"):
            break
        groups += res["cruises"]
        time.sleep(0.7)
    rows = []
    for g in groups:
        master = ((g.get("masterSailing") or {}).get("itinerary")) or {}
        for s in g.get("sailings") or []:
            own = s.get("itinerary") or {}
            it = merged(master, own)
            ship = merged(master.get("ship"), own.get("ship"))
            depart = (it.get("departurePort") or {}).get("name")
            ports, sea = [], 0
            for d in it.get("days") or []:
                names = [n for n in ((v.get("port") or {}).get("name") for v in d.get("ports") or []) if n]
                if names and all(n.lower() == "cruising" for n in names):
                    sea += 1
                for n in names:
                    if n.lower() != "cruising" and n != depart and n not in ports:
                        ports.append(n)
            raw = {}
            for p in s.get("stateroomClassPricing") or []:
                v = money((p.get("price") or {}).get("value"))
                if v and p.get("stateroomClass"):
                    raw[p["stateroomClass"]["id"]] = v
            cab = {"interior": raw.get("INTERIOR"), "outside": raw.get("OUTSIDE"), "balcony": raw.get("BALCONY"), "suite": raw.get("DELUXE")}
            start = (s.get("startDate") or "")[:10]
            code = own.get("code") or master.get("code")
            url = None
            if g.get("productViewLink"):
                u = urllib.parse.urlsplit(site + "/" + g["productViewLink"].lstrip("/"))
                q = dict(urllib.parse.parse_qsl(u.query))
                q.update({"sailDate": start, "packageCode": code or q.get("packageCode", "")})
                url = urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, urllib.parse.urlencode(q), ""))
            r = row(line, ship.get("name"), it.get("name"), it.get("sailingNights") or it.get("totalNights"), depart,
                    start, (s.get("endDate") or "")[:10], ports, sea, cab, url)
            if not r["price_from"] and raw:
                r["price_from"] = min(raw.values())
            rows.append(r)
    return rows


# ---------- Norwegian ----------
def pull_norwegian():
    base = "https://www.ncl.com"
    itins, seen, total, off = [], set(), None, 0
    while total is None or off < total:
        j = json.loads(http(f"{base}/api/v2/vacations/search?filterConfig=search-filters-configuration&limit=100&offset={off}"))
        total = j["total"]
        if not j["itineraries"]:
            break
        for it in j["itineraries"]:
            if it.get("bundleType") == "cruise" and it["code"] not in seen:
                seen.add(it["code"])
                itins.append(it)
        off += 100
        time.sleep(0.4)

    def one(it):
        out = []
        try:
            j = json.loads(http(f"{base}/api/vacations/sailings/{urllib.parse.quote(it['code'])}"))
        except Exception as e:
            print(f"  norwegian: {it['code']} failed: {e}", flush=True)
            return out
        by = {}
        for p in j.get("pricingStateRooms") or []:
            k = (p.get("sailStartDate") or "")[:10]
            o = by.setdefault(k, {"end": (p.get("sailEndDate") or "")[:10], "cab": {}, "pid": p.get("packageId")})
            v = money(p.get("combinedPrice"))
            if p.get("status") == "AVAILABLE" and v:
                t = p.get("stateroomType")
                o["cab"][t] = min(o["cab"].get(t, 1e9), v)
        depart = (it.get("embarkationPort") or {}).get("title")
        ports = []
        for p in it.get("portsOfCall") or []:
            if p.get("title") and p["title"] != depart and p["title"] not in ports:
                ports.append(p["title"])
        for start, o in by.items():
            c = o["cab"]
            suite = [x for x in (c.get("SUITE"), c.get("HAVEN")) if x]
            cab = {"interior": c.get("INSIDE"), "outside": c.get("OCEANVIEW"), "balcony": c.get("BALCONY"), "suite": min(suite) if suite else None}
            url = f"{base}/vacation-builder?itineraryCode={urllib.parse.quote(it['code'])}&packageId={urllib.parse.quote(str(o['pid']))}"
            out.append(row("Norwegian", (it.get("ship") or {}).get("title"), it.get("title"), (it.get("duration") or {}).get("days"),
                           depart, start, o["end"], ports, None, cab, url))
        time.sleep(0.25)
        return out

    rows = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for part in ex.map(one, itins):
            rows += part
    return rows


# ---------- Virgin Voyages ----------
def pull_virgin():
    html = http("https://www.virginvoyages.com/book/voyage-planner/find-a-voyage?currencyCode=USD", headers={"Accept": "text/html"})
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    nf = "".join(json.loads('"' + c + '"') for c in chunks)
    key = '"response":{"packages":['
    i = nf.index(key) + len(key) - 1
    packages, _ = json.JSONDecoder().raw_decode(nf, i)
    ships = {"SC": "Scarlet Lady", "VL": "Valiant Lady", "RS": "Resilient Lady", "BR": "Brilliant Lady"}
    cat = {"INSIDER": "interior", "SEA VIEW": "outside", "SEA TERRACE": "balcony"}
    rows = []
    for p in packages:
        for s in p.get("sailingList") or []:
            stops = s.get("ports") or []
            depart = stops[0]["name"] if stops else p.get("departurePortCode")
            ports = []
            for x in stops:
                if x.get("name") and x["name"] != depart and x["name"] not in ports:
                    ports.append(x["name"])
            nights = s.get("duration")
            sea = max(0, nights + 1 - len({x.get("day") for x in stops})) if stops and nights else None
            sp = s.get("startingPrice") or {}
            pp = round(sp["amount"] / 2, 2) if money(sp.get("amount")) else None  # quoted per cabin for two
            g = sp.get("minPricedGenericCategoryCode") or ""
            k = cat.get(g) or ("suite" if re.search("ROCKSTAR|SUITE", g) else "interior")
            url = ("https://www.virginvoyages.com/book/voyage-planner/pre-checkout?packageCode="
                   + urllib.parse.quote(s["packageCode"]) + "&voyageId=" + urllib.parse.quote(s["id"]))
            rows.append(row("Virgin Voyages", ships.get(s.get("shipCode"), s.get("shipCode")), p.get("packageName"), nights,
                            depart, s.get("startDate"), s.get("endDate"), ports, sea, {k: pp} if pp else {}, url))
    return rows


def pull_msc():
    import browser_lines
    return browser_lines.pull_msc(row)


def pull_princess():
    import browser_lines
    rows = browser_lines.pull_princess(row)
    if sum(1 for r in rows if r["price_from"]) < 0.8 * len(rows):
        raise RuntimeError("fewer than 80% of sailings came back with a price")
    return rows


PULLERS = [
    ("Royal Caribbean", lambda: pull_royal("Royal Caribbean", "https://www.royalcaribbean.com"), 2500),
    ("Celebrity", lambda: pull_royal("Celebrity", "https://www.celebritycruises.com", "C"), 1500),
    ("Norwegian", pull_norwegian, 1200),
    ("Virgin Voyages", pull_virgin, 200),
    ("MSC", pull_msc, 4000),
    ("Princess", pull_princess, 1500),
]


def hist_key(r):
    """Stable id for one sailing: its link when it has one, since two listings can share a ship and date."""
    if r.get("url"):
        return hashlib.md5(r["url"].encode()).hexdigest()[:14]
    return "|".join(str(r.get(k) or "") for k in ("line", "ship", "start_date", "nights", "departure_port"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev", default="")
    ap.add_argument("--history", default="")
    ap.add_argument("--out", default="out")
    ap.add_argument("--only", default="", help="comma-separated line names to pull; the rest are carried forward")
    a = ap.parse_args()
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    now = datetime.now(TZ)
    stamp, today = now.strftime("%Y-%m-%dT%H:%M"), now.strftime("%Y-%m-%d")

    prev = {"sailings": [], "lines": {}}
    if a.prev and os.path.exists(a.prev):
        prev = json.load(open(a.prev, encoding="utf-8"))
    prev_by_line = {}
    for r in prev.get("sailings", []):
        prev_by_line.setdefault(r["line"], []).append(r)
    lines = dict(prev.get("lines") or {l: prev.get("scraped_at", "") for l in prev_by_line})

    fresh = {}
    for name, fn, minimum in PULLERS:
        if only and name not in only:
            continue
        t0 = time.time()
        try:
            rows = fn()
            if len(rows) < minimum:
                raise RuntimeError(f"only {len(rows)} sailings, expected at least {minimum}")
            fresh[name] = rows
            lines[name] = stamp
            print(f"PULL {name}: OK {len(rows)} sailings, {sum(1 for r in rows if r['price_from'])} priced, {time.time() - t0:.0f}s", flush=True)
        except Exception as e:
            print(f"PULL {name}: FAILED {type(e).__name__}: {str(e)[:300]} (keeping previous data)", flush=True)

    rows = []
    for line in sorted(set(prev_by_line) | set(fresh)):
        rows += fresh.get(line) or prev_by_line.get(line, [])
    rows = [r for r in rows if (r.get("start_date") or "") >= today]
    for r in rows:
        r["region"] = regions.classify(r)
        r.pop("hist", None)

    # price history: record a point only when a sailing's lowest price changes
    history = {}
    if a.history and os.path.exists(a.history):
        history = json.load(open(a.history, encoding="utf-8"))
    live = set()
    changed = 0
    for r in rows:
        k = hist_key(r)
        live.add(k)
        if r["line"] not in fresh or not r["price_from"]:
            pts = history.get(k)
        else:
            pts = history.setdefault(k, [])
            if not pts or pts[-1][1] != r["price_from"]:
                if pts:
                    changed += 1
                pts.append([today, r["price_from"]])
        if pts and len(pts) > 1:
            r["hist"] = pts[-12:]
    history = {k: v for k, v in history.items() if k in live}

    rows.sort(key=lambda r: (r["start_date"], r["line"], r["ship"] or ""))
    os.makedirs(a.out, exist_ok=True)
    dump = lambda obj, name: json.dump(obj, open(os.path.join(a.out, name), "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
    dump({"scraped_at": stamp, "lines": lines, "sailings": rows}, "sailings.json")
    dump(history, "history.json")
    print(f"DONE {len(rows)} sailings, {len(fresh)} of {len(PULLERS)} lines refreshed, {changed} price changes, lines: {lines}", flush=True)
    if not fresh:
        sys.exit("No line could be pulled.")


if __name__ == "__main__":
    main()
