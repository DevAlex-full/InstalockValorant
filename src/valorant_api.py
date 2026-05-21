"""
valorant_api.py
Baseado na abordagem comprovada do VALORANT-Instalocker de SuppliedOrange.
Usa a lib 'valclient' que resolve toda a complexidade da API.

Otimização: get_pregame_info() retorna match_id E map_id em 1 única chamada.
"""

import os
import re
import logging
from valclient.client import Client

logger = logging.getLogger(__name__)

_SHOOTER_LOG = os.path.join(
    os.environ.get('LOCALAPPDATA', ''),
    'VALORANT', 'Saved', 'Logs', 'ShooterGame.log'
)

VALID_REGIONS = ['na', 'eu', 'ap', 'kr', 'br', 'latam', 'pbe']


def get_region() -> str:
    if not os.path.exists(_SHOOTER_LOG):
        return 'br'
    try:
        with open(_SHOOTER_LOG, 'rb') as f:
            content = f.read()
        for pattern in [rb'regions/([a-z]+)\]', rb'config/([a-z]+)\]']:
            m = re.search(pattern, content)
            if m:
                region = m.group(1).decode().lower()
                if region in VALID_REGIONS:
                    return region
        m = re.search(rb'glz-([a-z]+)[0-9-]', content)
        if m:
            region = m.group(1).decode().lower().rstrip('1')
            if region in VALID_REGIONS:
                return region
    except Exception:
        pass
    return 'br'


def get_client() -> Client:
    region = get_region()
    try:
        client = Client(region=region)
    except ValueError as e:
        raise ValueError(f"Região inválida '{region}': {e}")
    try:
        client.activate()
    except FileNotFoundError:
        raise FileNotFoundError(
            "Lockfile do Valorant não encontrado. "
            "Abra o Valorant e aguarde o menu principal."
        )
    except Exception as e:
        raise RuntimeError(f"Falha ao ativar client Valorant: {e}")
    return client


def get_pregame_info(client: Client) -> tuple[str | None, str | None]:
    """
    ⚡ Retorna (match_id, map_id) em UMA ÚNICA chamada de API.

    Antes eram 2 chamadas separadas:
      1. fetch_presence()       → detecta PREGAME
      2. pregame_fetch_match()  → pega match_id E map_id

    Agora ambas são feitas juntas, eliminando a latência extra.
    Retorna (None, None) se não estiver em agent select.
    """
    try:
        presence = client.fetch_presence(client.puuid)
        if not presence:
            return None, None

        match_data = presence.get('matchPresenceData', {})
        if not match_data:
            return None, None

        state = match_data.get('sessionLoopState', '')
        if state != 'PREGAME':
            return None, None

        # Uma única chamada para pegar match_id e map_id
        match  = client.pregame_fetch_match()
        return match.get('ID'), match.get('MapID')

    except Exception as e:
        err = str(e)
        if 'pre-game' in err.lower() or 'pregame' in err.lower():
            return None, None
        raise


def select_agent(client: Client, agent_id: str) -> bool:
    try:
        client.pregame_select_character(agent_id)
        return True
    except Exception as e:
        logger.error(f"Falha ao selecionar agente: {e}")
        return False


def lock_agent(client: Client, agent_id: str) -> bool:
    try:
        client.pregame_lock_character(agent_id)
        return True
    except Exception as e:
        logger.error(f"Falha ao travar agente: {e}")
        return False


def test_connection() -> dict:
    r = {
        'log_path':      _SHOOTER_LOG,
        'log_exists':    os.path.exists(_SHOOTER_LOG),
        'region':        None,
        'client_ok':     False,
        'puuid':         None,
        'presence_ok':   False,
        'session_state': None,
        'in_pregame':    False,
        'match_id':      None,
        'error':         None,
    }
    try:
        r['region']    = get_region()
        client         = get_client()
        r['client_ok'] = True
        r['puuid']     = client.puuid

        try:
            presence = client.fetch_presence(client.puuid)
            if presence:
                r['presence_ok']   = True
                match_data         = presence.get('matchPresenceData', {})
                r['session_state'] = match_data.get('sessionLoopState', 'N/A')
                if r['session_state'] == 'PREGAME':
                    match           = client.pregame_fetch_match()
                    r['match_id']   = match.get('ID')
                    r['in_pregame'] = bool(r['match_id'])
        except Exception as e:
            if 'pre-game' not in str(e).lower():
                r['error'] = f"Presence: {e}"

    except FileNotFoundError as e:
        r['error'] = str(e)
    except Exception as e:
        r['error'] = f"{type(e).__name__}: {e}"

    return r