#!/usr/bin/env python3
"""Incremental AHledger item metadata importer (keyless, standard library only).

Reads recipe item/reagent IDs, enriches a limited number per run, and publishes
only data explicitly returned by the documented Forever item endpoint.
Does NOT invent combat stats, effects, slots, or disenchant outputs.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / 'data' / 'recipes.json'
OUTPUT = ROOT / 'data' / 'items.json'
API = 'https://api.ahledger.com/v1/items/{}?game=forever'
MAX_PER_RUN = min(500, max(1, int(os.getenv('ITEMS_PER_RUN', '180'))))

def normalize(raw, item_id):
    """Conservative extraction; fields without upstream evidence stay absent."""
    if not isinstance(raw, dict):
        return None
    obj = raw.get('item') if isinstance(raw.get('item'), dict) else raw
    name = obj.get('name') or obj.get('itemName')
    if not isinstance(name, str) or not name.strip():
        return None
    out = {'id': str(item_id), 'name': name.strip(), 'source': 'AHledger',
           'sourceUrl': 'https://ahledger.com/items/' + str(item_id)}
    aliases = {
        'quality': ('quality', 'rarity'),
        'itemLevel': ('itemLevel', 'item_level', 'ilevel', 'level'),
        'requiredLevel': ('requiredLevel', 'required_level', 'levelRequired', 'requiredCharacterLevel'),
        'itemClass': ('itemClass', 'className', 'class', 'itemClassName'),
        'subclass': ('subclass', 'subClass', 'subclassName', 'itemSubClass'),
        'inventoryType': ('inventoryType', 'slot', 'equipSlot'),
        'icon': ('icon', 'iconName'),
        'vendorSellPrice': ('vendorSellPrice', 'sellPrice', 'vendorValue'),
        'description': ('description',),
        'bagSlots': ('bagSlots', 'containerSlots', 'numSlots'),
    }
    for dest, names in aliases.items():
        for field in names:
            value = obj.get(field)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool) and value != '':
                if dest in ('itemLevel', 'requiredLevel', 'vendorSellPrice', 'bagSlots'):
                    try: value = int(value)
                    except (ValueError, TypeError): continue
                    if value < 0: continue
                if dest == 'bagSlots' and (value < 1 or value > 100): continue
                if dest == 'icon' and not re.fullmatch(r'[a-zA-Z0-9_\-]{2,90}', str(value)):
                    continue  # avoid arbitrary external URLs from an upstream response
                out[dest] = value
                break
    # More advanced fields only if supplied as structured data; never inferred from name.
    if isinstance(obj.get('stats'), list):
        out['stats'] = [ {'name': str(x['name'])[:70], 'value': str(x['value'])[:80]}
                         for x in obj['stats'] if isinstance(x, dict) and 'name' in x and 'value' in x][:18]
    for key in ('useEffect', 'equipEffect', 'binding'):
        value = obj.get(key)
        if isinstance(value, str) and value.strip(): out[key] = value[:700]
    return out

def fetch(item_id):
    req = Request(API.format(item_id), headers={
        'User-Agent':'ProfessionWorkshop/0.9 (fan crafting tool; https://github.com/DVExperiments/Profession-Workshop)',
        'Accept':'application/json'})
    with urlopen(req, timeout=18) as response:
        return json.load(response)

def main():
    if not RECIPES.exists():
        sys.exit('Recipe file missing: run Update Forever recipe snapshot first')
    recipe_data = json.loads(RECIPES.read_text(encoding='utf-8'))
    ids = set()
    for r in recipe_data.get('recipes', []):
        for item in [ {'id': r.get('itemId')}, *(r.get('ingredients') or []) ]:
            value = str(item.get('id', '') or '').strip()
            if value.isdecimal() and int(value) > 0: ids.add(value)
    if not ids:
        sys.exit('No numeric item IDs in recipe snapshot; refusing empty export')
    existing = {}
    if OUTPUT.exists():
        saved = json.loads(OUTPUT.read_text(encoding='utf-8'))
        existing = {str(i['id']):i for i in saved.get('items', []) if isinstance(i, dict) and i.get('id')}
    old_unresolved = saved.get('unresolved', {}) if OUTPUT.exists() else {}
    if not isinstance(old_unresolved, dict): old_unresolved = {}
    unresolved = {str(k):str(v) for k,v in old_unresolved.items() if str(k) in ids}
    # Back off missing/error IDs for seven days instead of retrying them forever.
    now = dt.datetime.now(dt.timezone.utc)
    def due(item_id):
        previous = unresolved.get(item_id)
        if not previous: return True
        try: return now - dt.datetime.fromisoformat(previous) > dt.timedelta(days=7)
        except ValueError: return True
    pending = [item_id for item_id in sorted(ids - existing.keys(), key=int) if due(item_id)]
    print(f'Known: {len(existing)} items; recipe item IDs: {len(ids)}; pending: {len(pending)}', flush=True)
    new_count = 0
    failures = 0
    for index, item_id in enumerate(pending[:MAX_PER_RUN]):
        try:
            item = normalize(fetch(item_id), item_id)
            if item is not None:
                existing[item_id] = item
                unresolved.pop(item_id, None)
                new_count += 1
            else:
                failures += 1
                unresolved[item_id]=now.isoformat()
                print(f'No valid item record for {item_id}', flush=True)
        except (HTTPError, URLError, ValueError, TimeoutError) as ex:
            failures += 1
            unresolved[item_id]=now.isoformat()
            print(f'Error for item {item_id}: {ex}', file=sys.stderr, flush=True)
            if isinstance(ex, HTTPError) and ex.code in (429, 503):
                print('Source rate-limited; stopping this run to protect source.', flush=True)
                break
        time.sleep(.35)
    if new_count == 0 and not existing and failures == 0:
        sys.exit('No items retrieved. Existing dataset left untouched.')
    output = {
        'schema': 1, 'provider':'AHledger',
        'attribution':'Item metadata by AHledger — https://ahledger.com',
        'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
        'count':len(existing), 'knownRecipeItemIds':len(ids), 'unresolved':unresolved,
        'items':sorted(existing.values(), key=lambda o:int(o['id']))
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Saved {len(existing)} items; new={new_count}, unresolved={failures}, remaining ~{len(ids)-len(existing)}', flush=True)

if __name__ == '__main__': main()
