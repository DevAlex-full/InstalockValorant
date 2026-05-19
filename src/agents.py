"""
agents.py
Busca agentes + mapas via valorant-api.com (API pública, gratuita).
"""
import os, json, requests
from typing import List, Dict

AGENTS_API = "https://valorant-api.com/v1/agents?isPlayableCharacter=true&language=pt-BR"
MAPS_API   = "https://valorant-api.com/v1/maps?language=pt-BR"
AGENTS_CACHE = "agents_cache.json"
MAPS_CACHE   = "maps_cache.json"


def fetch_agents(agents_dir: str) -> List[Dict]:
    cache_path = os.path.join(agents_dir, AGENTS_CACHE)
    if os.path.exists(cache_path):
        try:
            agents = json.load(open(cache_path, encoding='utf-8'))
            if all(os.path.exists(os.path.join(agents_dir, f"{a['uuid']}.png")) for a in agents):
                return sorted(agents, key=lambda x: x['displayName'])
        except Exception:
            pass
    try:
        raw = requests.get(AGENTS_API, timeout=15).json().get('data', [])
    except Exception as e:
        print(f"[agents] Erro: {e}")
        return []
    agents = []
    for r in raw:
        icon_url = r.get('bustPortrait') or r.get('displayIcon') or ''
        agents.append({
            'uuid':        r['uuid'],
            'displayName': r['displayName'],
            'role':        (r.get('role') or {}).get('displayName', ''),
            'iconUrl':     icon_url,
        })
    sess = requests.Session()
    for a in agents:
        p = os.path.join(agents_dir, f"{a['uuid']}.png")
        if not os.path.exists(p) and a['iconUrl']:
            try:
                resp = sess.get(a['iconUrl'], timeout=10)
                resp.raise_for_status()
                open(p, 'wb').write(resp.content)
            except Exception:
                pass
    json.dump(agents, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    return sorted(agents, key=lambda x: x['displayName'])


def fetch_maps(assets_dir: str) -> List[Dict]:
    cache_path = os.path.join(assets_dir, MAPS_CACHE)
    if os.path.exists(cache_path):
        try:
            maps = json.load(open(cache_path, encoding='utf-8'))
            if all(os.path.exists(os.path.join(assets_dir, f"map_{m['uuid']}.png")) for m in maps):
                return maps
        except Exception:
            pass
    try:
        raw = requests.get(MAPS_API, timeout=15).json().get('data', [])
    except Exception as e:
        print(f"[maps] Erro: {e}")
        return []

    maps = []
    for r in raw:
        # Filtra mapas sem displayName real (tutorial, range, etc)
        name = r.get('displayName', '')
        if not name or name.lower() in ['the range', 'character select', 'menu']:
            continue
        maps.append({
            'uuid':        r['uuid'],
            'mapUrl':      r.get('mapUrl', ''),   # usado pelo pregame para identificar
            'displayName': name,
            'splash':      r.get('splash', ''),
            'listViewIcon': r.get('listViewIcon', ''),
        })

    sess = requests.Session()
    for m in maps:
        p = os.path.join(assets_dir, f"map_{m['uuid']}.png")
        icon = m['listViewIcon'] or m['splash']
        if not os.path.exists(p) and icon:
            try:
                resp = sess.get(icon, timeout=10)
                resp.raise_for_status()
                open(p, 'wb').write(resp.content)
            except Exception:
                pass

    json.dump(maps, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    return maps