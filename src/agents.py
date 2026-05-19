"""
agents.py
Busca e cacheia dados + ícones dos agentes via valorant-api.com (API pública, gratuita).
"""

import os
import json
import requests
from typing import List, Dict

API_URL   = "https://valorant-api.com/v1/agents?isPlayableCharacter=true&language=pt-BR"
CACHE_FILE = "agents_cache.json"


def fetch_agents(agents_dir: str) -> List[Dict]:
    """
    Retorna lista de agentes com UUID, nome e ícone local.
    - Na primeira execução: baixa da API e cacheia.
    - Nas próximas: usa cache local se imagens já existem.
    """
    cache_path = os.path.join(agents_dir, CACHE_FILE)

    # ── Tenta usar cache ──────────────────────────────────────────────────────
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding='utf-8') as f:
                agents = json.load(f)

            # Verifica se todas as imagens existem
            all_ok = all(
                os.path.exists(os.path.join(agents_dir, f"{a['uuid']}.png"))
                for a in agents
            )
            if all_ok:
                return sorted(agents, key=lambda x: x['displayName'])
        except Exception:
            pass

    # ── Busca da API ──────────────────────────────────────────────────────────
    try:
        resp = requests.get(API_URL, timeout=15)
        resp.raise_for_status()
        raw_agents = resp.json().get('data', [])
    except Exception as e:
        print(f"[agents] Erro ao buscar agentes: {e}")
        return []

    agents = []
    for raw in raw_agents:
        # Prefere bust portrait, fallback para display icon
        icon_url = raw.get('bustPortrait') or raw.get('displayIcon') or ''
        role_name = ''
        if raw.get('role'):
            role_name = raw['role'].get('displayName', '')

        agents.append({
            'uuid':        raw['uuid'],
            'displayName': raw['displayName'],
            'role':        role_name,
            'iconUrl':     icon_url,
        })

    # ── Download das imagens ──────────────────────────────────────────────────
    print(f"[agents] Baixando {len(agents)} ícones...")
    session = requests.Session()

    for agent in agents:
        img_path = os.path.join(agents_dir, f"{agent['uuid']}.png")
        if os.path.exists(img_path):
            continue
        if not agent['iconUrl']:
            continue
        try:
            img_resp = session.get(agent['iconUrl'], timeout=10)
            img_resp.raise_for_status()
            with open(img_path, 'wb') as f:
                f.write(img_resp.content)
        except Exception as e:
            print(f"[agents] Falha ao baixar ícone de {agent['displayName']}: {e}")

    # ── Salva cache ───────────────────────────────────────────────────────────
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(agents, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[agents] Não foi possível salvar cache: {e}")

    return sorted(agents, key=lambda x: x['displayName'])