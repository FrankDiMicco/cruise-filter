"""Check which cruise line data feeds answer from this machine."""
import json, urllib.request, urllib.error

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
RC_Q = "query CruiseSearch($filters: String, $sort: CruiseSearchSort, $pagination: CruiseSearchPagination) { cruiseSearch(filters: $filters, sort: $sort, pagination: $pagination) { results { total } } }"
RC_BODY = json.dumps({"operationName": "CruiseSearch", "query": RC_Q, "variables": {"filters": None, "sort": {"by": "RECOMMENDED"}, "pagination": {"count": 1, "skip": 0}}}).encode()
MSC_BODY = json.dumps({"requests": [{"indexName": "prod-en-us-itinerary-deduplication-relevance", "distinct": 0, "filters": "(noofAdults=2) AND (hasAir: false)", "hitsPerPage": 1, "page": 0}]}).encode()
J = {"Content-Type": "application/json", "Accept": "application/json"}
TESTS = [
    ("Royal Caribbean", "https://www.royalcaribbean.com/cruises/graph", RC_BODY, J, '"total"'),
    ("Celebrity", "https://www.celebritycruises.com/cruises/graph", RC_BODY, dict(J, brand="C"), '"total"'),
    ("Norwegian", "https://www.ncl.com/api/v2/vacations/search?filterConfig=search-filters-configuration&limit=1&offset=0", None, {"Accept": "application/json"}, '"itineraries"'),
    ("MSC", "https://www.msccruisesusa.com/api-search/1/indexes/*/queries", MSC_BODY, dict(J, **{"MSC-Locale": "en_US"}), '"nbHits"'),
    ("Princess", "https://www.princess.com/cruise-search/results/", None, {"Accept": "text/html"}, "__NEXT_DATA__"),
    ("Virgin Voyages", "https://www.virginvoyages.com/book/voyage-planner/find-a-voyage", None, {"Accept": "text/html"}, "sailingsAvailability"),
]
for name, url, body, headers, marker in TESTS:
    req = urllib.request.Request(url, data=body, headers=dict(headers, **{"User-Agent": UA}), method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            text = r.read().decode("utf-8", "replace")
            print(f"PROBE {name}: HTTP {r.status}, {len(text)} bytes, marker {'FOUND' if marker in text else 'missing'} | {text[:120]!r}")
    except urllib.error.HTTPError as e:
        print(f"PROBE {name}: HTTP {e.code} | {e.read()[:160]!r}")
    except Exception as e:
        print(f"PROBE {name}: FAILED {type(e).__name__}: {e}")
