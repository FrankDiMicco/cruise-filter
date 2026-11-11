# Cruise Filter

A personal cruise search filter covering Royal Caribbean, Celebrity, Norwegian, MSC, Princess, and Virgin Voyages.

Live site: https://frankdimicco.github.io/cruise-filter/

- `index.html` is the whole app. It loads `sailings.json` from the same folder.
- `scripts/pull.py` pulls fresh data and tracks price changes. `scripts/regions.py` assigns each sailing a part of the world.
- `.github/workflows/pull.yml` runs the pull every morning and publishes the result to the `gh-pages` branch, which is what the live site serves. The data files (`sailings.json`, `history.json`) live only on that branch.
- Royal Caribbean, Celebrity, Norwegian and Virgin Voyages refresh daily. MSC and Princess need a real browser, so their data is carried forward from the last manual pull.

Prices are snapshots from each cruise line's public search at the time shown in the app. Confirm on the cruise line's site before booking.
