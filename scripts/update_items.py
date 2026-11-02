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
    obj = raw
    # Public APIs may wrap a record in data, item or result.
    for _ in range(3):
        inner = next((obj.get(k) for k in ('item', 'data', 'result')
                      if isinstance(obj.get(k), dict)), None)
        if inner is None: break
        obj = inner
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

COMPANION = 'https://forevercompanion.io/api/v1/items/{}'
TOOLTIPS_PER_RUN = min(120, max(1, int(os.getenv('TOOLTIPS_PER_RUN', '45'))))

def fetch_companion(item_id):
    req = Request(COMPANION.format(item_id), headers={
        'User-Agent': 'ProfessionWorkshop/1.0 (community item details; https://github.com/DVExperiments/Profession-Workshop)',
        'Accept': 'application/json'})
    with urlopen(req, timeout=18) as response:
        return json.load(response)

def companion_detail(raw, item_id):
    if not isinstance(raw, dict): return None
    obj = raw.get('data', raw)
    if not isinstance(obj, dict): return None
    if str(obj.get('id', obj.get('itemId', item_id))) != str(item_id): return None
    tooltip = obj.get('tooltip')
    lines = []
    if isinstance(tooltip, list):
        for line in tooltip[:35]:
            if isinstance(line, dict) and isinstance(line.get('left'), str):
                lines.append({'left':line['left'][:300],
                              'right':str(line.get('right') or '')[:160],
                              'kind':str(line.get('kind') or 'plain')[:30]})
    if not lines: return None
    return {'tooltipLines': lines, 'tooltipSource': 'Forever Companion',
            'tooltipSourceUrl': 'https://forevercompanion.io/developers',
            'tooltipConfidence': 'client/community-sourced'}

def due_tooltip(item_id, now, previous):
    try:
        return now - dt.datetime.fromisoformat(previous[item_id]) > dt.timedelta(days=30)
    except (KeyError, ValueError, TypeError):
        return True

def main():
    if not RECIPES.exists():
        sys.exit('Recipe file missing: run Update Forever recipe snapshot first')
    recipe_data = json.loads(RECIPES.read_text(encoding='utf-8'))
    ids = set()
    names = {}
    for r in recipe_data.get('recipes', []):
        for item in [ {'id': r.get('itemId')}, *(r.get('ingredients') or []) ]:
            value = str(item.get('id', '') or '').strip()
            if value.isdecimal() and int(value) > 0:
                ids.add(value)
                if item.get('name'): names[value] = item['name']
        output_id = str(r.get('itemId') or '').strip()
        if output_id.isdecimal() and r.get('name'): names[output_id] = r['name']
    if not ids:
        sys.exit('No numeric item IDs in recipe snapshot; refusing empty export')
    existing = {}
    if OUTPUT.exists():
        saved = json.loads(OUTPUT.read_text(encoding='utf-8'))
        existing = {str(i['id']):i for i in saved.get('items', []) if isinstance(i, dict) and i.get('id')}
    old_unresolved = saved.get('unresolved', {}) if OUTPUT.exists() else {}
    if not isinstance(old_unresolved, dict): old_unresolved = {}
    unresolved = {str(k):str(v) for k,v in old_unresolved.items() if str(k) in ids}
    tooltip_attempts = saved.get('tooltipAttempts', {}) if OUTPUT.exists() else {}
    if not isinstance(tooltip_attempts, dict): tooltip_attempts = {}
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
    # Supplement AHledger with actual in-game tooltip lines where publicly catalogued.
    # Forever Companion covers dungeon, quest and reputation items, not all recipes.
    output_ids = {str(r.get('itemId')) for r in recipe_data.get('recipes', []) if str(r.get('itemId','')).isdecimal()}
    tooltip_ids = [x for x in sorted(ids, key=lambda i:(i not in output_ids, int(i)))
                   if not existing.get(x, {}).get('tooltipLines')
                   and (x not in tooltip_attempts or due_tooltip(x, now, tooltip_attempts))]
    tooltip_added = 0
    tooltip_missing = 0
    for item_id in tooltip_ids[:TOOLTIPS_PER_RUN]:
        try:
            more = companion_detail(fetch_companion(item_id), item_id)
            if more:
                record = existing.setdefault(item_id, {'id':item_id,
                    'name':names.get(item_id, f'Item #{item_id}'),
                    'source':'Recipe catalog',
                    'sourceUrl':f'https://ahledger.com/items/{item_id}'})
                record.update(more)
                tooltip_attempts.pop(item_id, None)
                tooltip_added += 1
            else:
                tooltip_attempts[item_id] = now.isoformat()
                tooltip_missing += 1
        except (HTTPError, URLError, ValueError, TimeoutError) as ex:
            tooltip_attempts[item_id] = now.isoformat()
            tooltip_missing += 1
            if isinstance(ex, HTTPError) and ex.code == 429:
                print('Companion rate limit reached: pausing tooltip enrichment')
                break
        time.sleep(.55)
    print(f'Tooltip enrichment: {tooltip_added} with lines, {tooltip_missing} unavailable; coverage is partial', flush=True)
    if new_count == 0 and not existing:
        sys.exit(f'Item API returned no usable item records ({failures} failed). Check response schema and availability; refusing a misleading successful workflow.')
    output = {
        'schema': 1, 'provider':'AHledger',
        'attribution':'Item metadata by AHledger — https://ahledger.com',
        'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
        'count':len(existing), 'knownRecipeItemIds':len(ids), 'unresolved':unresolved,
        'tooltipAttempts':tooltip_attempts,
        'withProperties':sum(bool(set(i) & {'quality','itemLevel','requiredLevel','itemClass','subclass','bagSlots','description'}) for i in existing.values()),
        'withTooltips':sum(bool(i.get('tooltipLines')) for i in existing.values()),
        'items':sorted(existing.values(), key=lambda o:int(o['id']))
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Saved {len(existing)} items; new={new_count}, unresolved={failures}, remaining ~{len(ids)-len(existing)}', flush=True)

if __name__ == '__main__': main()
