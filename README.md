# Profession Workshop v0.9 — Item Codex

An independent fan-made, GitHub Pages crafting journal for World of Warcraft: Forever.

## What's new

- A fourth **Item Library** page with searchable crafted items and reagents.
- A separate, incremental static **item information snapshot** at `data/items.json`.
- Better item tooltip and selected recipe detail panels; they show only what the imported source actually supplies.
- An automatic, keyless **Update Forever item information** workflow to fetch item properties from AHledger's documented `GET /v1/items/{itemId}?game=forever` endpoint.
- Item provenance and source links. Bag slots, bonuses, potion effects and stats remain **unknown** unless they appear in data (or user-verified notes).
- All previous v0.8 features preserved: 2,144+ recipe import, crafting chains, favourites, My Bank, disenchant estimates, local backups and mobile interface.

## Installation on GitHub Pages

1. Upload the package contents to the repository root, preserving `.github/workflows/`, `scripts/`, `assets/`, and `data/`.
2. **Do not overwrite or delete your existing `data/recipes.json`.** The zip deliberately omits it.
3. In **Actions → Update Forever item information → Run workflow**, run the new updater. It pulls 180 items per run to respect source load, skips missing IDs temporarily, and commits the growing `data/items.json` snapshot.
4. After a successful run and Pages deployment, refresh the website and open **Item Library**. Run the action again to add more of the known recipe item IDs. It also runs daily.
5. `data/items.json` initially contains 0 items; the action must complete before metadata appears. The app already indexes recipe names and reagents even when item metadata is pending.

The item updater is independent of the existing `Update Forever recipe snapshot` action. It can run after recipes are populated, and it needs GitHub Actions **Read and write permissions** under Settings → Actions → General to commit files.

## Data honesty

AHledger documents that its item endpoint provides names, rarity, item level, item class, minimum level, vendor value, and icon. Some returned records might provide extra structured fields; only those fields are displayed. The app does *not* fill in missing bag capacities, spell effects, equipment stats, binding, or drop information from generic Classic Era guesses. Source attribution: [AHledger](https://ahledger.com).

Forever items can differ from Classic and the data evolves. AHledger does not guarantee full in-game tooltip/effect descriptions via its documented item endpoint. The *Item Library* is a real searchable database, but **full detailed effects are an ongoing data-coverage limitation**.

The item importer is designed for the public API but has not been live-run here (network access is restricted). If it fails, inspect the GitHub Actions log. A failing request does not delete any existing completed item records.

## Static hosting

Everything runs on GitHub Pages without an application server or browser-to-AHledger CORS calls. Inventory, notes and favourites are stored in the current browser and can be backed up to JSON.
