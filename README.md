# Cruise Filter

A personal cruise search filter covering Royal Caribbean, Celebrity, Norwegian, MSC, Princess, and Virgin Voyages.

- `index.html` is the whole app. It loads `sailings.json` from the same folder.
- `sailings.json` holds every sailing with dates, ports, per-person prices by cabin type, a region tag, and a link to the sailing on the cruise line's site.
- `scripts/regions.py` assigns each sailing a part of the world from its itinerary name and ports.

Prices are snapshots from each cruise line's public search at the time shown in the app. Confirm on the cruise line's site before booking.
