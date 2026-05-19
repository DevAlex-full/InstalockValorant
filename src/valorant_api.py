"""
valorant_api.py
Baseado na abordagem comprovada do VALORANT-Instalocker de SuppliedOrange.
Usa a lib 'valclient' que resolve toda a complexidade da API.

Fonte de referência: https://github.com/SuppliedOrange/VALORANT-Instalocker
"""

import os
import re
import logging
from valclient.client import Client

logger = logging.getLogger(__name__)

# ── Caminho do log do jogo (onde a região está registrada) ────────────────────
_SHOOTER_LOG = os.path.join(
    os.environ.get('LOCALAPPDATA', ''),
    'VALORANT', 'Saved', 'Logs', 'ShooterGame.log'
)

# ── Regiões válidas aceitas pelo valclient ────────────────────────────────────
VALID_REGIONS = ['na', 'eu', 'ap', 'kr', 'br', 'latam', 'pbe']


def get_region() -> str:
    """
    Lê a região do log do Valorant (ShooterGame.log).
    Essa é a abordagem correta — o próprio jogo registra qual servidor usa.
    Retorna 'br' como fallback se não encontrar.
    """
    if not os.path.exists(_SHOOTER_LOG):
        logger.warning(f"ShooterGame.log não encontrado: {_SHOOTER_LOG}")
        return 'br'

    try:
        with open(_SHOOTER_LOG, 'rb') as f:
            content = f.read()

        # Padrão 1: "regions/br]"
        m = re.search(rb'regions/([a-z]+)\]', content)
        if m:
            region = m.group(1).decode().lower()
            if region in VALID_REGIONS:
                logger.info(f"Região detectada (padrão 1): {region}")
                return region

        # Padrão 2: "config/br]"
        m = re.search(rb'config/([a-z]+)\]', content)
        if m:
            region = m.group(1).decode().lower()
            if region in VALID_REGIONS:
                logger.info(f"Região detectada (padrão 2): {region}")
                return region

        # Padrão 3: glz-br / glz-na etc no log
        m = re.search(rb'glz-([a-z]+)[0-9-]', content)
        if m:
            region = m.group(1).decode().lower().rstrip('1')
            if region in VALID_REGIONS:
                logger.info(f"Região detectada (GLZ): {region}")
                return region

    except Exception as e:
        logger.error(f"Erro ao ler ShooterGame.log: {e}")

    logger.warning("Região não detectada, usando fallback 'br'")
    return 'br'


def get_client() -> Client:
    """
    Cria e ativa um client valclient com a região correta.
    Lança exceção com mensagem clara se algo falhar.
    """
    region = get_region()
    logger.info(f"Criando client para região: {region}")

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


def get_pregame_match_id(client: Client) -> str | None:
    """
    Verifica se o jogador está em agent select via presence data.
    Retorna o match_id se estiver, None caso contrário.
    """
    try:
        presence = client.fetch_presence(client.puuid)
        if not presence:
            return None

        match_data = presence.get('matchPresenceData', {})
        if not match_data:
            return None

        state = match_data.get('sessionLoopState', '')
        if state != 'PREGAME':
            return None

        match = client.pregame_fetch_match()
        return match.get('ID')

    except Exception as e:
        err = str(e)
        if 'pre-game' in err.lower() or 'pregame' in err.lower():
            return None   # Normal — fora do pregame
        raise


def get_current_map(client) -> str | None:
    """
    Retorna o mapUrl do mapa atual (ex: '/Game/Maps/Triad/Triad')
    ou None se não estiver em agent select.
    """
    try:
        match = client.pregame_fetch_match()
        return match.get('MapID')  # ex: /Game/Maps/Port/Port
    except Exception:
        return None


def select_agent(client, agent_id: str) -> bool:
    """Seleciona (hover) o agente."""
    try:
        client.pregame_select_character(agent_id)
        return True
    except Exception as e:
        logger.error(f"Falha ao selecionar agente: {e}")
        return False


def lock_agent(client: Client, agent_id: str) -> bool:
    """Trava o agente definitivamente."""
    try:
        client.pregame_lock_character(agent_id)
        return True
    except Exception as e:
        logger.error(f"Falha ao travar agente: {e}")
        return False


def test_connection() -> dict:
    """Diagnóstico completo da conexão."""
    r = {
        'log_path':       _SHOOTER_LOG,
        'log_exists':     os.path.exists(_SHOOTER_LOG),
        'region':         None,
        'client_ok':      False,
        'puuid':          None,
        'presence_ok':    False,
        'session_state':  None,
        'in_pregame':     False,
        'match_id':       None,
        'error':          None,
    }
    try:
        r['region'] = get_region()
        client      = get_client()
        r['client_ok'] = True
        r['puuid']     = client.puuid

        try:
            presence = client.fetch_presence(client.puuid)
            if presence:
                r['presence_ok']  = True
                match_data        = presence.get('matchPresenceData', {})
                r['session_state'] = match_data.get('sessionLoopState', 'N/A')

                if r['session_state'] == 'PREGAME':
                    match      = client.pregame_fetch_match()
                    r['match_id']   = match.get('ID')
                    r['in_pregame'] = bool(r['match_id'])
        except Exception as e:
            if 'pre-game' not in str(e).lower():
                r['error'] = f"Presence error: {e}"

    except FileNotFoundError as e:
        r['error'] = str(e)
    except Exception as e:
        r['error'] = f"{type(e).__name__}: {e}"

    return r