# Profession Workshop v1.1 — Item tooltip lookup repair

This update keeps the existing recipe and item snapshots unchanged.

## What's fixed

- Distinguishes an imported item record from an actual in-game description.
- Looks up item descriptions **on demand** from Forever Warcraft DB's public tooltip API when an item or recipe is selected.
- Renders remote tooltip text as escaped text (never injects untrusted HTML).
- Caches successful lookups in this browser; includes a retry button and direct item-source link.
- Shows clear service/network error messages instead of silently claiming a description exists.

## Deployment

Upload `index.html` from this package over the existing file in the repository root. Other files are unchanged. **Do not delete or replace `data/recipes.json` or `data/items.json`.**

## Data limitations

The provided items.json contains 360 records but only 2 item tooltips, out of 2,533 distinct item IDs. The existing importer is not a source of full tooltip descriptions. The new live lookup uses a third-party endpoint that documents cross-origin support, but its coverage and uptime for Forever have not been verified here. On lookup failure it provides a clear message and source link. This is not an offline tooltip database. Existing crafting and locally saved data continue to work if the service is unavailable.

Source documentation: https://classic.warcraftdb.com/tool/tooltip
