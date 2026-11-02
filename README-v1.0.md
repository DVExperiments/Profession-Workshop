# Profession Workshop — v1.0 item data repair

## What changed

- AHledger item importer now handles nested JSON wrappers (`data`, `item`, `result`).
- Source errors that produce no item records now cause a failed workflow instead of a misleading green success.
- The importer also looks up actual tooltip lines through the public Forever Companion item endpoint for a limited subset of the recipe item IDs, rate-limited and incremental. That API mainly covers dungeon and quest items, so **not every crafted item will have tooltip text**.
- Item Library now reports total item records, records with basic properties, and records with real tooltip lines separately.
- Journal detail panels and hover tooltips can render imported tooltip lines.
- No effects, stats, bag capacities or item descriptions are inferred or fabricated.

## Installation

Upload `index.html`, `journal.css`, and `scripts/update_items.py` to the corresponding paths on your `main` branch. Keep all your existing `data/recipes.json` and `data/items.json` files; they are intentionally not in this update.

Then run **Actions → Update Forever item information → Run workflow** again. The existing workflow calls `scripts/update_items.py`, so its YAML does not need replacement.

After the successful run inspect `data/items.json`: `count`, `withProperties`, `withTooltips`. Refresh GitHub Pages and open the Item Library. A valid item record does not necessarily have a description. Repeat scheduled updates to expand coverage.

## Source limitations

AHledger's documented item API provides item identification and basic metadata, not comprehensive in-game effects. Forever Companion provides an additional public endpoint with tooltip lines for the items in its narrower catalogue. Missing tooltip data is reported as missing; this is not a complete Forever item-effect database.

This package has passed local Python/JavaScript syntax checks and synthetic parser checks, but external endpoints and browser deployment could not be tested from this environment.
