#!/usr/bin/env python3
"""Build a static, no-key recipe catalog from AHledger's documented public crafting endpoint.

Requires only Python's standard library. Does not create fabricated recipes on errors.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'recipes.json'
PROFESSIONS = ['Alchemy','Blacksmithing','Enchanting','Engineering','Leatherworking','Tailoring','Cooking','First Aid','Mining','Herbalism','Skinning','Fishing']
MARKET = os.environ.get('AHL_MARKET', 'forever.pvp.horde.us')
BASE = 'https://api.ahledger.com/v1/crafting/'


def fetch(profession):
    params=urllib.parse.urlencode({'profession': profession, 'all': '1', 'limit': '5000'})
    url=BASE + urllib.parse.quote(MARKET, safe='.') + '?' + params
    req=urllib.request.Request(url, headers={'User-Agent':'ProfessionWorkshop/0.3 (GitHub Pages recipe mirror; attribution on every page)', 'Accept':'application/json'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                return json.load(response)
        except (urllib.error.URLError, ValueError) as exc:
            if attempt == 2:
                raise RuntimeError(f'{profession}: {exc}') from exc
            time.sleep(2*(attempt+1))


def parse(raw, profession):
    if not isinstance(raw, dict) or not isinstance(raw.get('recipes'), list):
        raise ValueError(f'Unexpected response for {profession}; expected recipes array')
    results=[]
    for row in raw['recipes']:
        if not isinstance(row,dict): continue
        detail=row.get('recipe') if isinstance(row.get('recipe'),dict) else row
        product=row.get('result') if isinstance(row.get('result'),dict) else {}
        reagents=row.get('reagents') or detail.get('reagents') or []
        if not isinstance(reagents,list): continue
        item_id=product.get('id') or detail.get('resultItemId') or detail.get('itemId')
        spell_id=detail.get('spellId') or detail.get('id')
        title=product.get('name') or detail.get('name')
        if not isinstance(title,str) or not title.strip() or not isinstance(reagents,list): continue
        ingredients=[]
        for reagent in reagents:
            if not isinstance(reagent,dict): continue
            rid=reagent.get('id') or reagent.get('itemId')
            rname=reagent.get('name')
            qty=reagent.get('qty') or reagent.get('quantity') or reagent.get('count') or 1
            if not isinstance(rname,str) or not rname.strip(): continue
            try: qty=max(1,int(qty))
            except (TypeError,ValueError): continue
            ingredients.append({'id':str(rid) if rid is not None else '', 'name':rname,'qty':qty})
        try: yield_qty=max(1,int(product.get('qtyMin') or detail.get('yield') or 1))
        except (TypeError,ValueError): yield_qty=1
        results.append({'key':f"{profession}:{spell_id or item_id or title}", 'spellId':spell_id, 'itemId':str(item_id) if item_id is not None else '', 'name':title, 'profession':detail.get('profession') or profession, 'skill':detail.get('skillRequired'), 'acquisition':detail.get('acquisition') or '', 'yield':yield_qty, 'yieldMax':product.get('qtyMax'), 'ingredients':ingredients, 'origin':'AHledger', 'sourceUrl':'https://ahledger.com/crafting', 'notes':''})
    return results


def main():
    all_rows=[]; counts={}; errors=[]
    for profession in PROFESSIONS:
        try:
            payload=fetch(profession)
            rows=parse(payload,profession)
            counts[profession]=len(rows)
            all_rows.extend(rows)
            print(f'{profession}: {len(rows)} records',flush=True)
        except Exception as exc:
            errors.append(str(exc));print(f'ERROR: {exc}', file=sys.stderr)
        time.sleep(.3)
    # A partial export must never overwrite a previously complete snapshot.
    if errors or len(all_rows)<100:
        print(f'Import aborted; {len(all_rows)} records and {len(errors)} errors. Existing data untouched.',file=sys.stderr)
        sys.exit(1)
    unique={row['key']:row for row in all_rows}
    output={'schema':1,'provider':'AHledger','attribution':'Recipe data from AHledger — https://ahledger.com', 'market':MARKET, 'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(), 'count':len(unique),'professionCounts':counts,'recipes':list(unique.values())}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(output,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    print(f'Wrote {len(unique)} recipes to {OUT}')

if __name__=='__main__': main()
