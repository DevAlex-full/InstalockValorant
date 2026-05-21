"""
main.py — InstalockValorant v1.1.0
Features:
  - Grid de agentes com ícones oficiais
  - Seleção de agente por mapa (ou padrão)
  - Agente secundário como fallback
  - Instalock instantâneo (0ms delay, threads paralelas)
  - Notificação sonora + desktop ao travar
  - Atualização automática (checa nova versão no GitHub)
  - Suporte a múltiplos perfis
  - Hotkey global configurável
  - Diagnóstico integrado
"""

import customtkinter as ctk
from PIL import Image
import threading
import time
import json
import os
import sys
import winsound
import urllib.request
import webbrowser
from pynput import keyboard as pynput_kb

from valorant_api import (
    get_client, get_pregame_info,
    select_agent, lock_agent, test_connection, get_region
)
from agents import fetch_agents, fetch_maps

# ── Versão atual ───────────────────────────────────────────────────────────────
APP_VERSION    = "1.1.0"
GITHUB_API_URL = "https://api.github.com/repos/DevAlex-full/InstalockValorant/releases/latest"

# ── Paths ──────────────────────────────────────────────────────────────────────
APP_DIR     = os.path.join(os.environ.get('APPDATA', '.'), 'InstalockValorant')
CONFIG_FILE = os.path.join(APP_DIR, 'config.json')
AGENTS_DIR  = os.path.join(APP_DIR, 'agents')
os.makedirs(APP_DIR,    exist_ok=True)
os.makedirs(AGENTS_DIR, exist_ok=True)

def _get_asset(filename: str) -> str:
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.join(os.path.dirname(__file__), '..', 'assets')
    return os.path.join(base, filename)

# ── Paleta ─────────────────────────────────────────────────────────────────────
C = {
    'bg':           '#0F1923',
    'bg_header':    '#0B1520',
    'bg_card':      '#131F2A',
    'bg_card_sel':  '#1E0C10',
    'bg_infobar':   '#0D1720',
    'accent':       '#FF4655',
    'accent_dim':   '#7A1E27',
    'green':        '#00C853',
    'orange':       '#FF8C00',
    'border':       '#1C2D3A',
    'border_sel':   '#FF4655',
    'text':         '#FFFFFF',
    'text_dim':     '#6B8499',
    'text_mid':     '#A8BBC8',
}

# ── Config ─────────────────────────────────────────────────────────────────────
DEFAULT_CFG = {
    'active_profile':    'Principal',
    'profiles': {
        'Principal': {
            'default_agent_id':   None,
            'default_agent_name': None,
            'fallback_agent_id':  None,
            'fallback_agent_name': None,
            'map_agents':         {},
        }
    },
    'hotkey':         'F1',
    'sound_enabled':  True,
}

def load_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            data = json.load(open(CONFIG_FILE, encoding='utf-8'))
            # Migra config antiga (sem perfis) para novo formato
            if 'profiles' not in data:
                old_agent_id   = data.get('default_agent_id')
                old_agent_name = data.get('default_agent_name')
                old_map_agents = data.get('map_agents', {})
                data = dict(DEFAULT_CFG)
                data['profiles']['Principal']['default_agent_id']   = old_agent_id
                data['profiles']['Principal']['default_agent_name'] = old_agent_name
                data['profiles']['Principal']['map_agents']         = old_map_agents
            return data
    except Exception:
        pass
    return json.loads(json.dumps(DEFAULT_CFG))

def save_config(cfg: dict):
    json.dump(cfg, open(CONFIG_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

# ── Hotkey parser ──────────────────────────────────────────────────────────────
def parse_hotkey(s: str):
    parts   = [p.strip().lower() for p in s.split('+')]
    mod_map = {'ctrl': pynput_kb.Key.ctrl, 'shift': pynput_kb.Key.shift, 'alt': pynput_kb.Key.alt}
    fkey_map = {f'f{i}': getattr(pynput_kb.Key, f'f{i}') for i in range(1, 25)}
    mods, trigger = set(), None
    for p in parts:
        if p in mod_map:    mods.add(mod_map[p])
        elif p in fkey_map: trigger = fkey_map[p]
        else:
            try: trigger = pynput_kb.KeyCode.from_char(p)
            except Exception: pass
    return frozenset(mods), trigger

# ── Notificação sonora ─────────────────────────────────────────────────────────
def play_lock_sound():
    """Toca um beep duplo de sucesso via winsound (sem dependências extras)."""
    try:
        winsound.Beep(880, 120)
        time.sleep(0.05)
        winsound.Beep(1100, 180)
    except Exception:
        pass

# ── Verificação de atualização ─────────────────────────────────────────────────
def check_for_update() -> dict | None:
    """
    Checa a última release no GitHub.
    Retorna {'version': str, 'url': str} se houver versão mais nova, None caso contrário.
    """
    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={'User-Agent': f'InstalockValorant/{APP_VERSION}'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data       = json.loads(resp.read().decode())
            latest_tag = data.get('tag_name', '').lstrip('v')
            html_url   = data.get('html_url', '')

            # Compara versão
            def ver_tuple(v):
                try: return tuple(int(x) for x in v.split('.'))
                except: return (0,)

            if ver_tuple(latest_tag) > ver_tuple(APP_VERSION):
                return {'version': latest_tag, 'url': html_url}
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════════════════════
class InstalockApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.cfg        = load_config()
        self.hotkey_str = self.cfg.get('hotkey', 'F1')
        self.is_active  = False
        self.lock_fired = False
        self.last_match = None

        # Mapa selecionado na UI
        self.selected_map_uuid = None
        self.selected_map_name = 'Padrão'

        # Dados
        self.agents     = []
        self.maps       = []
        self.agent_cards = {}
        self.agent_imgs  = {}
        self.map_btns    = {}

        # Hotkey
        self._pressed_keys = set()
        self._hk_mods, self._hk_trigger = parse_hotkey(self.hotkey_str)
        self._kb_listener = None

        self._build_window()
        self._build_ui()
        self._start_kb_listener()
        self._start_data_load()
        self._start_polling()
        self._check_update_async()

    # ── Perfil ativo ──────────────────────────────────────────────────────────
    @property
    def profile(self) -> dict:
        name = self.cfg.get('active_profile', 'Principal')
        return self.cfg['profiles'].setdefault(name, {
            'default_agent_id': None, 'default_agent_name': None,
            'fallback_agent_id': None, 'fallback_agent_name': None,
            'map_agents': {}
        })

    # ── Window ────────────────────────────────────────────────────────────────
    def _build_window(self):
        ctk.set_appearance_mode("dark")
        self.title(f"InstalockValorant v{APP_VERSION}")
        self.geometry("1080x760")
        self.minsize(900, 640)
        self.resizable(True, True)
        self.configure(fg_color=C['bg'])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        ico_path = _get_asset('instalock_logo.ico')
        png_path = _get_asset('instalock_logo.png')
        try:
            self.iconbitmap(ico_path)
        except Exception:
            try:
                from PIL import ImageTk
                pil_icon = Image.open(png_path).resize((32, 32), Image.LANCZOS)
                tk_icon  = ImageTk.PhotoImage(pil_icon)
                self.iconphoto(True, tk_icon)
                self._icon_ref = tk_icon
            except Exception:
                pass

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=C['bg_header'], corner_radius=0, height=68)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        logo_f = ctk.CTkFrame(hdr, fg_color='transparent')
        logo_f.pack(side='left', padx=20)
        try:
            pil_logo = Image.open(_get_asset('instalock_logo.png')).resize((38, 38), Image.LANCZOS)
            ctk_logo = ctk.CTkImage(pil_logo, size=(38, 38))
            self._header_logo_ref = ctk_logo
            ctk.CTkLabel(logo_f, image=ctk_logo, text='').pack(side='left', padx=(0, 8))
        except Exception:
            ctk.CTkLabel(logo_f, text='⚡', font=ctk.CTkFont(size=22), text_color=C['accent']).pack(side='left')
        ctk.CTkLabel(logo_f, text='INSTALOCK', font=ctk.CTkFont(family='Impact', size=22),
                     text_color=C['accent']).pack(side='left')
        ctk.CTkLabel(logo_f, text=' VALORANT', font=ctk.CTkFont(family='Impact', size=22),
                     text_color=C['text']).pack(side='left')

        right = ctk.CTkFrame(hdr, fg_color='transparent')
        right.pack(side='right', padx=16)

        # Botão som
        self.sound_btn = ctk.CTkButton(right,
            text='🔊' if self.cfg.get('sound_enabled', True) else '🔇',
            fg_color='#1A2B38', hover_color='#243D50',
            border_color=C['border'], border_width=1,
            corner_radius=8, width=44, height=36,
            font=ctk.CTkFont(size=16),
            text_color=C['text_mid'],
            command=self._toggle_sound
        )
        self.sound_btn.pack(side='right', padx=(8, 0))

        # Botão diagnóstico
        ctk.CTkButton(right, text='🔍 Testar',
            fg_color='#1A2B38', hover_color='#243D50',
            border_color=C['border'], border_width=1,
            corner_radius=8, width=90, height=36,
            font=ctk.CTkFont(size=12, weight='bold'),
            text_color=C['text_mid'],
            command=self._run_diagnostic
        ).pack(side='right', padx=(8, 0))

        # Hotkey
        self.hotkey_btn = ctk.CTkButton(right,
            text=f'🔑  {self.hotkey_str}',
            fg_color=C['bg_card'], hover_color='#1E2F3D',
            border_color=C['border'], border_width=1,
            corner_radius=8, width=130, height=36,
            font=ctk.CTkFont(size=12, weight='bold'),
            text_color=C['text_mid'],
            command=self._change_hotkey
        )
        self.hotkey_btn.pack(side='right', padx=(8, 0))

        # Badge ATIVO/INATIVO
        self.badge_frame = ctk.CTkFrame(right, fg_color=C['accent'], corner_radius=8, height=36, width=110)
        self.badge_frame.pack(side='right')
        self.badge_frame.pack_propagate(False)
        self.badge_lbl = ctk.CTkLabel(self.badge_frame, text='● INATIVO',
            font=ctk.CTkFont(size=12, weight='bold'), text_color='white')
        self.badge_lbl.place(relx=0.5, rely=0.5, anchor='center')

        # Separador vermelho
        ctk.CTkFrame(self, fg_color=C['accent'], height=2, corner_radius=0).pack(fill='x')

        # ── Info bar ──────────────────────────────────────────────────────────
        info = ctk.CTkFrame(self, fg_color=C['bg_infobar'], corner_radius=0, height=46)
        info.pack(fill='x')
        info.pack_propagate(False)

        ctk.CTkLabel(info, text='PERFIL:', font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_dim']).pack(side='left', padx=(16, 4))
        self.profile_var = ctk.StringVar(value=self.cfg.get('active_profile', 'Principal'))
        self.profile_menu = ctk.CTkOptionMenu(info,
            variable=self.profile_var,
            values=list(self.cfg['profiles'].keys()),
            fg_color=C['bg_card'], button_color=C['border'],
            button_hover_color='#1E2F3D',
            dropdown_fg_color=C['bg_card'],
            text_color=C['accent'],
            font=ctk.CTkFont(size=12, weight='bold'),
            width=120, height=28,
            command=self._switch_profile
        )
        self.profile_menu.pack(side='left', padx=(0, 4))

        ctk.CTkButton(info, text='+', width=28, height=28,
            fg_color=C['bg_card'], hover_color='#1E2F3D',
            border_color=C['border'], border_width=1,
            font=ctk.CTkFont(size=14, weight='bold'),
            text_color=C['green'],
            command=self._new_profile
        ).pack(side='left', padx=(0, 16))

        ctk.CTkFrame(info, fg_color=C['border'], width=1, height=28).pack(side='left', padx=4)

        ctk.CTkLabel(info, text='AGENTE:', font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_dim']).pack(side='left', padx=(8, 4))
        self.agent_lbl = ctk.CTkLabel(info,
            text=self.profile.get('default_agent_name') or 'Nenhum',
            font=ctk.CTkFont(size=13, weight='bold'),
            text_color=C['accent'] if self.profile.get('default_agent_name') else C['text_dim'])
        self.agent_lbl.pack(side='left')

        ctk.CTkLabel(info, text='▸', font=ctk.CTkFont(size=11),
                     text_color=C['text_dim']).pack(side='left', padx=4)

        ctk.CTkLabel(info, text='FALLBACK:', font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_dim']).pack(side='left', padx=(0, 4))
        self.fallback_lbl = ctk.CTkLabel(info,
            text=self.profile.get('fallback_agent_name') or 'Nenhum',
            font=ctk.CTkFont(size=12),
            text_color=C['orange'] if self.profile.get('fallback_agent_name') else C['text_dim'])
        self.fallback_lbl.pack(side='left')

        ctk.CTkLabel(info, text='MAPA:', font=ctk.CTkFont(size=11, weight='bold'),
                     text_color=C['text_dim']).pack(side='left', padx=(20, 4))
        self.map_lbl = ctk.CTkLabel(info, text='Padrão',
            font=ctk.CTkFont(size=13, weight='bold'), text_color=C['text_mid'])
        self.map_lbl.pack(side='left')

        self.hint_lbl = ctk.CTkLabel(info,
            text=f'{self.hotkey_str} ativar  ·  Clique: agente principal  ·  Ctrl+Clique: fallback',
            font=ctk.CTkFont(size=10), text_color=C['text_dim'])
        self.hint_lbl.pack(side='right', padx=16)

        # ── Body ──────────────────────────────────────────────────────────────
        self.body = ctk.CTkFrame(self, fg_color=C['bg'], corner_radius=0)
        self.body.pack(fill='both', expand=True)

        # Painel mapas
        self.map_panel = ctk.CTkFrame(self.body, fg_color=C['bg_header'], corner_radius=0, width=170)
        self.map_panel.pack(side='left', fill='y')
        self.map_panel.pack_propagate(False)
        ctk.CTkLabel(self.map_panel, text='MAPAS',
            font=ctk.CTkFont(size=10, weight='bold'),
            text_color=C['text_dim']).pack(pady=(14, 8))
        self.map_scroll = ctk.CTkScrollableFrame(self.map_panel, fg_color='transparent',
            scrollbar_button_color=C['border'])
        self.map_scroll.pack(fill='both', expand=True, padx=6, pady=(0, 8))

        ctk.CTkFrame(self.body, fg_color=C['border'], width=1, corner_radius=0).pack(side='left', fill='y')

        # Painel agentes
        self.agent_panel = ctk.CTkFrame(self.body, fg_color=C['bg'], corner_radius=0)
        self.agent_panel.pack(side='left', fill='both', expand=True)

        self.loading_frame = ctk.CTkFrame(self.agent_panel, fg_color=C['bg'])
        self.loading_frame.pack(fill='both', expand=True)
        ctk.CTkLabel(self.loading_frame, text='⏳  Baixando dados dos agentes e mapas...',
            font=ctk.CTkFont(size=15), text_color=C['text_dim']
        ).place(relx=0.5, rely=0.5, anchor='center')

        self.scroll = ctk.CTkScrollableFrame(self.agent_panel,
            fg_color=C['bg'], scrollbar_button_color=C['border'])

        # Status bar
        self.status_bar = ctk.CTkLabel(self, text='Aguardando Valorant...',
            font=ctk.CTkFont(size=11), text_color=C['text_dim'])
        self.status_bar.pack(side='bottom', pady=7)
        ctk.CTkFrame(self, fg_color=C['border'], height=1, corner_radius=0).pack(side='bottom', fill='x')

    # ── Data load ─────────────────────────────────────────────────────────────
    def _start_data_load(self):
        self._set_status('⏳ Baixando agentes e mapas...')
        threading.Thread(target=self._load_thread, daemon=True).start()

    def _load_thread(self):
        agents = fetch_agents(AGENTS_DIR)
        maps   = fetch_maps(AGENTS_DIR)
        self.agents = agents
        self.maps   = maps
        if agents:
            self.after(0, lambda: self._render_all(agents, maps))
        else:
            self.after(0, lambda: self._set_status('❌ Falha ao carregar agentes.'))

    def _render_all(self, agents, maps):
        self.loading_frame.pack_forget()
        self._render_map_tabs(maps)
        self.scroll.pack(fill='both', expand=True, padx=6, pady=4)
        COLS = 4
        for c in range(COLS):
            self.scroll.columnconfigure(c, weight=1)
        for idx, agent in enumerate(agents):
            row, col = divmod(idx, COLS)
            self._make_agent_card(agent, row, col)
        self._set_status(
            f'✅ {len(agents)} agentes, {len(maps)} mapas  |  '
            f'Clique = principal  |  Ctrl+Clique = fallback  |  {self.hotkey_str} para ativar'
        )

    # ── Map tabs ──────────────────────────────────────────────────────────────
    def _render_map_tabs(self, maps):
        self._make_map_btn(None, 'Padrão (todos os mapas)')
        for m in maps:
            self._make_map_btn(m['uuid'], m['displayName'])
        self._highlight_map_btn(None)

    def _make_map_btn(self, uuid, name):
        img_path = os.path.join(AGENTS_DIR, f"map_{uuid}.png") if uuid else None
        btn_frame = ctk.CTkFrame(self.map_scroll, fg_color=C['bg_card'],
            corner_radius=8, border_width=1, border_color=C['border'], cursor='hand2')
        btn_frame.pack(fill='x', pady=3, padx=2)

        if img_path and os.path.exists(img_path):
            try:
                pil = Image.open(img_path).resize((130, 48), Image.LANCZOS)
                ctk_img = ctk.CTkImage(pil, size=(130, 48))
                self.agent_imgs[f'map_{uuid}'] = ctk_img
                ctk.CTkLabel(btn_frame, image=ctk_img, text='').pack(pady=(6, 2))
            except Exception:
                pass

        lbl = ctk.CTkLabel(btn_frame,
            text=name[:18] + ('…' if len(name) > 18 else ''),
            font=ctk.CTkFont(size=10, weight='bold'), text_color=C['text_mid'])
        lbl.pack(pady=(2, 6), padx=6)

        def on_click(e=None, u=uuid, n=name):
            self._select_map(u, n)

        btn_frame.bind('<Button-1>', on_click)
        lbl.bind('<Button-1>', on_click)
        self.map_btns[uuid] = btn_frame

    def _select_map(self, uuid, name):
        self.selected_map_uuid = uuid
        self.selected_map_name = 'Padrão' if uuid is None else name
        self._highlight_map_btn(uuid)
        self.map_lbl.configure(text=self.selected_map_name)

        if uuid is None:
            agent_name = self.profile.get('default_agent_name', '')
        else:
            agent_id = self.profile.get('map_agents', {}).get(uuid)
            agent_name = next((a['displayName'] for a in self.agents if a['uuid'] == agent_id), '')

        self.agent_lbl.configure(
            text=agent_name or 'Nenhum',
            text_color=C['accent'] if agent_name else C['text_dim'])
        self._highlight_active_agent(uuid)
        self._set_status(f'🗺️ {self.selected_map_name}  |  Principal: {agent_name or "—"}  |  Clique p/ definir')

    def _highlight_map_btn(self, active_uuid):
        for uuid, frame in self.map_btns.items():
            if uuid == active_uuid:
                frame.configure(fg_color=C['bg_card_sel'], border_color=C['border_sel'])
            else:
                frame.configure(fg_color=C['bg_card'], border_color=C['border'])

    # ── Agent cards ───────────────────────────────────────────────────────────
    def _make_agent_card(self, agent: dict, row: int, col: int):
        uuid   = agent['uuid']
        is_sel = uuid == self.profile.get('default_agent_id')
        is_fb  = uuid == self.profile.get('fallback_agent_id')

        card = ctk.CTkFrame(self.scroll,
            fg_color=C['bg_card_sel'] if is_sel else C['bg_card'],
            corner_radius=10, border_width=2,
            border_color=C['border_sel'] if is_sel else (C['orange'] if is_fb else C['border']),
            cursor='hand2')
        card.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')

        img_path = os.path.join(AGENTS_DIR, f"{uuid}.png")
        if os.path.exists(img_path):
            try:
                pil = Image.open(img_path).resize((88, 88), Image.LANCZOS)
                ctk_img = ctk.CTkImage(pil, size=(88, 88))
                self.agent_imgs[uuid] = ctk_img
                ctk.CTkLabel(card, image=ctk_img, text='').pack(pady=(10, 3))
            except Exception:
                ctk.CTkLabel(card, text='?', font=ctk.CTkFont(size=28),
                             text_color=C['text_dim']).pack(pady=(10, 3))
        else:
            ctk.CTkLabel(card, text='?', font=ctk.CTkFont(size=28),
                         text_color=C['text_dim']).pack(pady=(10, 3))

        ctk.CTkLabel(card, text=agent['displayName'],
            font=ctk.CTkFont(size=11, weight='bold'),
            text_color=C['text'] if is_sel else C['text_mid']).pack(pady=(0, 2))

        if agent.get('role'):
            ctk.CTkLabel(card, text=agent['role'].upper(),
                font=ctk.CTkFont(size=9),
                text_color=C['accent'] if is_sel else (C['orange'] if is_fb else C['text_dim'])
            ).pack(pady=(0, 8))
        else:
            ctk.CTkFrame(card, fg_color='transparent', height=8).pack()

        def handler(e=None, aid=uuid, aname=agent['displayName']):
            if e and (e.state & 0x4):  # Ctrl pressionado
                self._set_fallback(aid, aname)
            else:
                self._select_agent(aid, aname)

        card.bind('<Button-1>', handler)
        for child in card.winfo_children():
            child.bind('<Button-1>', handler)

        self.agent_cards[uuid] = card

    def _select_agent(self, agent_id: str, agent_name: str):
        """Define agente principal (clique normal)."""
        map_uuid = self.selected_map_uuid
        if map_uuid is None:
            self.profile['default_agent_id']   = agent_id
            self.profile['default_agent_name'] = agent_name
        else:
            self.profile.setdefault('map_agents', {})[map_uuid] = agent_id
        save_config(self.cfg)
        self._highlight_active_agent(map_uuid)
        self.agent_lbl.configure(text=agent_name, text_color=C['accent'])
        self._set_status(f'✅ Principal: {agent_name} → {self.selected_map_name}')

    def _set_fallback(self, agent_id: str, agent_name: str):
        """Define agente fallback (Ctrl+Clique)."""
        self.profile['fallback_agent_id']   = agent_id
        self.profile['fallback_agent_name'] = agent_name
        save_config(self.cfg)
        self._highlight_active_agent(self.selected_map_uuid)
        self.fallback_lbl.configure(text=agent_name, text_color=C['orange'])
        self._set_status(f'🔶 Fallback definido: {agent_name}')

    def _highlight_active_agent(self, map_uuid):
        if map_uuid is None:
            active_id   = self.profile.get('default_agent_id')
        else:
            active_id   = self.profile.get('map_agents', {}).get(map_uuid) or self.profile.get('default_agent_id')
        fallback_id = self.profile.get('fallback_agent_id')

        for uuid, card in self.agent_cards.items():
            is_sel = (uuid == active_id)
            is_fb  = (uuid == fallback_id and not is_sel)
            card.configure(
                fg_color=C['bg_card_sel'] if is_sel else C['bg_card'],
                border_color=C['border_sel'] if is_sel else (C['orange'] if is_fb else C['border'])
            )
            for child in card.winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    txt = child.cget('text')
                    if txt and txt not in ('', '?'):
                        if txt == txt.upper() and 2 < len(txt) < 25:
                            child.configure(text_color=C['accent'] if is_sel else (C['orange'] if is_fb else C['text_dim']))
                        else:
                            child.configure(text_color=C['text'] if is_sel else C['text_mid'])

    def _get_agent_for_map(self, map_id: str | None) -> tuple[str | None, str, str | None, str]:
        """Retorna (agent_id, agent_name, fallback_id, fallback_name)."""
        agent_id = agent_name = fallback_id = fallback_name = None

        if map_id:
            matched = next(
                (m for m in self.maps if map_id.lower() in m.get('mapUrl', '').lower()), None)
            if matched:
                aid = self.profile.get('map_agents', {}).get(matched['uuid'])
                if aid:
                    aname = next((a['displayName'] for a in self.agents if a['uuid'] == aid), '')
                    agent_id, agent_name = aid, aname

        if not agent_id:
            agent_id   = self.profile.get('default_agent_id')
            agent_name = self.profile.get('default_agent_name', '')

        fallback_id   = self.profile.get('fallback_agent_id')
        fallback_name = self.profile.get('fallback_agent_name', '')

        return agent_id, agent_name, fallback_id, fallback_name

    # ── Perfis ────────────────────────────────────────────────────────────────
    def _switch_profile(self, profile_name: str):
        self.cfg['active_profile'] = profile_name
        save_config(self.cfg)
        p = self.profile
        self.agent_lbl.configure(
            text=p.get('default_agent_name') or 'Nenhum',
            text_color=C['accent'] if p.get('default_agent_name') else C['text_dim'])
        self.fallback_lbl.configure(
            text=p.get('fallback_agent_name') or 'Nenhum',
            text_color=C['orange'] if p.get('fallback_agent_name') else C['text_dim'])
        self._highlight_active_agent(self.selected_map_uuid)
        self._set_status(f'👤 Perfil: {profile_name}')

    def _new_profile(self):
        dialog = ctk.CTkInputDialog(text='Nome do novo perfil:', title='Novo Perfil')
        name = dialog.get_input()
        if name and name.strip() and name.strip() not in self.cfg['profiles']:
            name = name.strip()
            self.cfg['profiles'][name] = {
                'default_agent_id': None, 'default_agent_name': None,
                'fallback_agent_id': None, 'fallback_agent_name': None,
                'map_agents': {}
            }
            self.cfg['active_profile'] = name
            save_config(self.cfg)
            self.profile_menu.configure(values=list(self.cfg['profiles'].keys()))
            self.profile_var.set(name)
            self._switch_profile(name)

    # ── Som ───────────────────────────────────────────────────────────────────
    def _toggle_sound(self):
        self.cfg['sound_enabled'] = not self.cfg.get('sound_enabled', True)
        save_config(self.cfg)
        self.sound_btn.configure(text='🔊' if self.cfg['sound_enabled'] else '🔇')
        self._set_status(f"🔊 Som: {'Ativado' if self.cfg['sound_enabled'] else 'Desativado'}")

    # ── Atualização ───────────────────────────────────────────────────────────
    def _check_update_async(self):
        threading.Thread(target=self._check_update_thread, daemon=True).start()

    def _check_update_thread(self):
        update = check_for_update()
        if update:
            self.after(0, lambda u=update: self._show_update_banner(u))

    def _show_update_banner(self, update: dict):
        banner = ctk.CTkFrame(self, fg_color='#1A2800', corner_radius=0, height=38)
        banner.pack(fill='x', after=self.status_bar)
        banner.pack_propagate(False)

        ctk.CTkLabel(banner,
            text=f'🆕  Nova versão disponível: v{update["version"]}',
            font=ctk.CTkFont(size=12, weight='bold'),
            text_color=C['green']).pack(side='left', padx=16)

        ctk.CTkButton(banner, text='Baixar agora →',
            fg_color=C['green'], hover_color='#009900',
            corner_radius=6, width=120, height=26,
            font=ctk.CTkFont(size=11, weight='bold'),
            text_color='white',
            command=lambda u=update['url']: webbrowser.open(u)
        ).pack(side='left', padx=8)

        ctk.CTkButton(banner, text='✕',
            fg_color='transparent', hover_color='#1C2D3A',
            width=30, height=26, text_color=C['text_dim'],
            command=banner.destroy
        ).pack(side='right', padx=8)

    # ── Hotkey ────────────────────────────────────────────────────────────────
    def _start_kb_listener(self):
        self._hk_mods, self._hk_trigger = parse_hotkey(self.hotkey_str)
        self._pressed_keys.clear()
        if self._kb_listener:
            try: self._kb_listener.stop()
            except Exception: pass
        self._kb_listener = pynput_kb.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release)
        self._kb_listener.start()

    def _on_key_press(self, key):
        self._pressed_keys.add(key)
        self._check_hotkey()

    def _on_key_release(self, key):
        self._pressed_keys.discard(key)

    def _check_hotkey(self):
        if not self._hk_trigger: return
        trigger_hit = self._hk_trigger in self._pressed_keys
        if not trigger_hit:
            for k in self._pressed_keys:
                if hasattr(k, 'char') and hasattr(self._hk_trigger, 'char'):
                    if k.char == self._hk_trigger.char:
                        trigger_hit = True; break
        if not trigger_hit: return
        pressed_mods = set()
        for k in self._pressed_keys:
            if k in (pynput_kb.Key.ctrl_l, pynput_kb.Key.ctrl_r, pynput_kb.Key.ctrl):
                pressed_mods.add(pynput_kb.Key.ctrl)
            elif k in (pynput_kb.Key.shift_l, pynput_kb.Key.shift_r, pynput_kb.Key.shift):
                pressed_mods.add(pynput_kb.Key.shift)
            elif k in (pynput_kb.Key.alt_l, pynput_kb.Key.alt_r, pynput_kb.Key.alt):
                pressed_mods.add(pynput_kb.Key.alt)
        if frozenset(pressed_mods) == self._hk_mods:
            self._toggle()

    def _toggle(self):
        self.is_active  = not self.is_active
        self.lock_fired = False
        self.after(0, self._update_badge)

    def _update_badge(self):
        if self.is_active:
            self.badge_frame.configure(fg_color=C['green'])
            self.badge_lbl.configure(text='● ATIVO')
            agent = self.profile.get('default_agent_name') or 'sem agente'
            self._set_status(f'🟢 ATIVO ({agent}) | Aguardando agent select...')
        else:
            self.badge_frame.configure(fg_color=C['accent'])
            self.badge_lbl.configure(text='● INATIVO')
            self._set_status('🔴 Instalock desativado.')

    def _change_hotkey(self):
        dialog = ctk.CTkInputDialog(
            text='Digite a nova hotkey:\n(ex: F1, F2, ctrl+shift+l)', title='Alterar Hotkey')
        val = dialog.get_input()
        if val and val.strip():
            self.hotkey_str = val.strip()
            self.hotkey_btn.configure(text=f'🔑  {self.hotkey_str}')
            self.hint_lbl.configure(
                text=f'{self.hotkey_str} ativar  ·  Clique: principal  ·  Ctrl+Clique: fallback')
            self.cfg['hotkey'] = self.hotkey_str
            save_config(self.cfg)
            self._start_kb_listener()
            self._set_status(f'✅ Hotkey: {self.hotkey_str}')

    # ── Poll loop ─────────────────────────────────────────────────────────────
    def _start_polling(self):
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _poll_loop(self):
        client, client_time = None, 0
        REFRESH, RETRY = 45 * 60, 10

        while True:
            now = time.time()
            need_refresh = (
                (client is None     and now - client_time > RETRY) or
                (client is not None and now - client_time > REFRESH)
            )
            if need_refresh:
                try:
                    client      = get_client()
                    client_time = now
                    region      = get_region().upper()
                    self.after(0, lambda r=region: self._set_status(
                        f'✅ Conectado | Região: {r} | {self.hotkey_str} para ativar'))
                except FileNotFoundError:
                    client, client_time = None, now
                    self.after(0, lambda: self._set_status('⚠️ Valorant não detectado. Abra o jogo...'))
                except Exception as e:
                    client, client_time = None, now
                    self.after(0, lambda m=str(e)[:80]: self._set_status(f'❌ {m}'))

            if self.is_active and client:
                try:
                    # ⚡ Uma única chamada → match_id + map_id simultaneamente
                    match_id, map_id = get_pregame_info(client)

                    if match_id and match_id != self.last_match:
                        self.last_match = match_id
                        self.lock_fired = False
                    elif not match_id and self.last_match:
                        self.last_match, self.lock_fired = None, False

                    if match_id and not self.lock_fired:
                        self.lock_fired = True

                        agent_id, agent_name, fallback_id, fallback_name = self._get_agent_for_map(map_id)

                        if not agent_id:
                            self.after(0, lambda: self._set_status('⚠️ Nenhum agente configurado!'))
                            self.lock_fired = False
                        else:
                            sound_enabled = self.cfg.get('sound_enabled', True)

                            def _fire(aid=agent_id, aname=agent_name,
                                      fid=fallback_id, fname=fallback_name,
                                      c=client, snd=sound_enabled):
                                # Tenta principal em paralelo (select + lock)
                                t1 = threading.Thread(target=select_agent, args=(c, aid), daemon=True)
                                t2 = threading.Thread(target=lock_agent,   args=(c, aid), daemon=True)
                                t1.start(); t2.start()
                                t1.join();  t2.join()

                                # Toca som de sucesso
                                if snd:
                                    threading.Thread(target=play_lock_sound, daemon=True).start()

                                self.after(0, lambda n=aname: self._set_status(
                                    f'🔒 {n} travado! GG 🎉'))

                            threading.Thread(target=_fire, daemon=True).start()

                except Exception as e:
                    err = str(e)
                    if any(x in err.lower() for x in ['401','403','unauthorized','token','lockfile']):
                        client, client_time = None, 0
                    elif 'pre-game' not in err.lower():
                        self.after(0, lambda m=err[:70]: self._set_status(f'❌ {m}'))

            time.sleep(0.01)

    # ── Diagnostic ────────────────────────────────────────────────────────────
    def _run_diagnostic(self):
        self._set_status('🔍 Testando conexão...')
        def do_test():
            r = test_connection()
            lines = []
            if r['error']:
                lines.append(f"❌ ERRO: {r['error']}")
            else:
                lines.append(f"✅ Lockfile encontrado")
                lines.append(f"   {r['lockfile_path']}")
                ok = "✅" if r['tokens_ok'] else "❌"
                lines.append(f"{ok} Tokens Bearer + Entitlement")
                if r['puuid']:
                    lines.append(f"✅ PUUID: {str(r['puuid'])[:28]}...")
                lines.append(f"🌍 Região: {str(r.get('region','?')).upper()}")
                ok = "✅" if r['presence_ok'] else "❌"
                lines.append(f"{ok} Presence: {r.get('session_state','N/A')}")
                if r['in_pregame']:
                    lines.append("🎯 EM AGENT SELECT! Instalock vai funcionar!")
                else:
                    lines.append("ℹ️ Fora de agent select — teste durante a seleção")
            self.after(0, lambda: self._show_diag_dialog(lines))
            self.after(0, lambda: self._set_status(lines[0]))
        threading.Thread(target=do_test, daemon=True).start()

    def _show_diag_dialog(self, lines):
        win = ctk.CTkToplevel(self)
        win.title("Diagnóstico de Conexão")
        win.geometry("580x420")
        win.configure(fg_color=C['bg'])
        win.grab_set()
        ctk.CTkLabel(win, text="🔍 Resultado do Diagnóstico",
            font=ctk.CTkFont(size=15, weight='bold'), text_color=C['text']).pack(pady=(20, 10))
        frame = ctk.CTkFrame(win, fg_color=C['bg_card'], corner_radius=10)
        frame.pack(fill='x', padx=20, pady=5)
        for line in lines:
            color = C['accent'] if line.startswith('❌') else (C['green'] if line.startswith('✅') else C['text_mid'])
            ctk.CTkLabel(frame, text=line, font=ctk.CTkFont(size=11), text_color=color,
                anchor='w', wraplength=500, justify='left').pack(anchor='w', padx=15, pady=3)
        ctk.CTkButton(win, text="Fechar",
            fg_color=C['accent'], hover_color=C['accent_dim'],
            command=win.destroy, width=100).pack(pady=15)

    def _set_status(self, msg: str):
        self.status_bar.configure(text=msg)

    def _on_close(self):
        if self._kb_listener:
            try: self._kb_listener.stop()
            except Exception: pass
        self.destroy()


if __name__ == '__main__':
    app = InstalockApp()
    app.mainloop()