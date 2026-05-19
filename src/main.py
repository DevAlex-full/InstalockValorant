"""
main.py
InstalockValorant — Instalock automático via API local do Valorant.
UI: CustomTkinter (dark theme, estilo Valorant)
"""

import customtkinter as ctk
from PIL import Image
import threading
import time
import json
import os
import sys

# pynput para hotkey global (sem precisar de admin no Windows)
from pynput import keyboard as pynput_kb

from valorant_api import get_client, get_pregame_match_id, select_agent, lock_agent, test_connection, get_region
from agents import fetch_agents

# ─── Paths ────────────────────────────────────────────────────────────────────
APP_DIR    = os.path.join(os.environ.get('APPDATA', '.'), 'InstalockValorant')
CONFIG_FILE = os.path.join(APP_DIR, 'config.json')
AGENTS_DIR  = os.path.join(APP_DIR, 'agents')

os.makedirs(APP_DIR,   exist_ok=True)
os.makedirs(AGENTS_DIR, exist_ok=True)

# ─── Cores (paleta Valorant) ──────────────────────────────────────────────────
C = {
    'bg':           '#0F1923',
    'bg_header':    '#0B1520',
    'bg_card':      '#131F2A',
    'bg_card_sel':  '#1E0C10',
    'bg_infobar':   '#0D1720',
    'accent':       '#FF4655',
    'accent_dim':   '#7A1E27',
    'green':        '#00C853',
    'border':       '#1C2D3A',
    'border_sel':   '#FF4655',
    'text':         '#FFFFFF',
    'text_dim':     '#6B8499',
    'text_mid':     '#A8BBC8',
    'scrollbar':    '#1C2D3A',
}

# ─── Config helpers ───────────────────────────────────────────────────────────
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'agent_id': None, 'agent_name': None, 'hotkey': 'F1'}


def save_config(cfg: dict):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ─── Hotkey parser ────────────────────────────────────────────────────────────
def parse_hotkey(hotkey_str: str):
    """
    Converte string como 'F1', 'ctrl+shift+l' em conjunto de teclas pynput.
    Retorna (modifiers: frozenset, key) para comparação com eventos.
    """
    parts = [p.strip().lower() for p in hotkey_str.split('+')]
    mod_map = {
        'ctrl':  pynput_kb.Key.ctrl,
        'shift': pynput_kb.Key.shift,
        'alt':   pynput_kb.Key.alt,
        'cmd':   pynput_kb.Key.cmd,
    }
    fkey_map = {f'f{i}': getattr(pynput_kb.Key, f'f{i}') for i in range(1, 25)}

    mods = set()
    trigger = None

    for part in parts:
        if part in mod_map:
            mods.add(mod_map[part])
        elif part in fkey_map:
            trigger = fkey_map[part]
        else:
            try:
                trigger = pynput_kb.KeyCode.from_char(part)
            except Exception:
                pass

    return frozenset(mods), trigger


# ─── Main App ─────────────────────────────────────────────────────────────────
class InstalockApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.cfg                = load_config()
        self.selected_agent_id  = self.cfg.get('agent_id')
        self.selected_agent_name= self.cfg.get('agent_name', '')
        self.hotkey_str         = self.cfg.get('hotkey', 'F1')

        self.is_active    = False
        self.lock_fired   = False
        self.last_match   = None

        self.agent_cards  = {}   # uuid -> (frame, name_label)
        self.agent_imgs   = {}   # uuid -> CTkImage (mantém referência)

        # Hotkey state
        self._pressed_keys = set()
        self._hk_mods, self._hk_trigger = parse_hotkey(self.hotkey_str)
        self._kb_listener = None

        self._build_window()
        self._build_ui()
        self._start_kb_listener()
        self._start_agent_load()
        self._start_polling()

    # ══════════════════════════════════════════════════════════════════════════
    # Window & UI
    # ══════════════════════════════════════════════════════════════════════════

    def _build_window(self):
        ctk.set_appearance_mode("dark")
        self.title("InstalockValorant")
        self.geometry("980x700")
        self.resizable(False, False)
        self.configure(fg_color=C['bg'])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=C['bg_header'], corner_radius=0, height=68)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        # Logo / título
        logo_frame = ctk.CTkFrame(hdr, fg_color='transparent')
        logo_frame.pack(side='left', padx=20)

        ctk.CTkLabel(
            logo_frame, text='⚡',
            font=ctk.CTkFont(size=22),
            text_color=C['accent']
        ).pack(side='left')

        ctk.CTkLabel(
            logo_frame, text=' INSTALOCK',
            font=ctk.CTkFont(family='Impact', size=22),
            text_color=C['accent']
        ).pack(side='left')

        ctk.CTkLabel(
            logo_frame, text=' VALORANT',
            font=ctk.CTkFont(family='Impact', size=22),
            text_color=C['text']
        ).pack(side='left')

        # Lado direito do header
        right = ctk.CTkFrame(hdr, fg_color='transparent')
        right.pack(side='right', padx=16)

        # Botão diagnóstico
        ctk.CTkButton(
            right,
            text='🔍 Testar',
            fg_color='#1A2B38',
            hover_color='#243D50',
            border_color=C['border'],
            border_width=1,
            corner_radius=8,
            width=90, height=36,
            font=ctk.CTkFont(size=12, weight='bold'),
            text_color=C['text_mid'],
            command=self._run_diagnostic
        ).pack(side='right', padx=(8, 0))

        # Botão hotkey
        self.hotkey_btn = ctk.CTkButton(
            right,
            text=f'🔑  {self.hotkey_str}',
            fg_color=C['bg_card'],
            hover_color='#1E2F3D',
            border_color=C['border'],
            border_width=1,
            corner_radius=8,
            width=130, height=36,
            font=ctk.CTkFont(size=12, weight='bold'),
            text_color=C['text_mid'],
            command=self._change_hotkey
        )
        self.hotkey_btn.pack(side='right', padx=(8, 0))

        # Badge status
        self.badge_frame = ctk.CTkFrame(
            right,
            fg_color=C['accent'],
            corner_radius=8,
            height=36, width=110
        )
        self.badge_frame.pack(side='right')
        self.badge_frame.pack_propagate(False)

        self.badge_lbl = ctk.CTkLabel(
            self.badge_frame,
            text='● INATIVO',
            font=ctk.CTkFont(size=12, weight='bold'),
            text_color='white'
        )
        self.badge_lbl.place(relx=0.5, rely=0.5, anchor='center')

        # ── Separador vermelho ────────────────────────────────────────────────
        sep = ctk.CTkFrame(self, fg_color=C['accent'], height=2, corner_radius=0)
        sep.pack(fill='x')

        # ── Info bar ──────────────────────────────────────────────────────────
        info = ctk.CTkFrame(self, fg_color=C['bg_infobar'], corner_radius=0, height=46)
        info.pack(fill='x')
        info.pack_propagate(False)

        ctk.CTkLabel(
            info, text='AGENTE:',
            font=ctk.CTkFont(size=11, weight='bold'),
            text_color=C['text_dim']
        ).pack(side='left', padx=(16, 8))

        self.agent_lbl = ctk.CTkLabel(
            info,
            text=self.selected_agent_name or 'Nenhum selecionado',
            font=ctk.CTkFont(size=13, weight='bold'),
            text_color=C['accent'] if self.selected_agent_name else C['text_dim']
        )
        self.agent_lbl.pack(side='left')

        self.hint_lbl = ctk.CTkLabel(
            info,
            text=f'Pressione {self.hotkey_str} para ativar  ·  Clique num agente para selecionar',
            font=ctk.CTkFont(size=11),
            text_color=C['text_dim']
        )
        self.hint_lbl.pack(side='right', padx=16)

        # ── Loading placeholder ───────────────────────────────────────────────
        self.loading_frame = ctk.CTkFrame(self, fg_color=C['bg'])
        self.loading_frame.pack(fill='both', expand=True)

        self.loading_lbl = ctk.CTkLabel(
            self.loading_frame,
            text='⏳  Baixando dados dos agentes...',
            font=ctk.CTkFont(size=15),
            text_color=C['text_dim']
        )
        self.loading_lbl.place(relx=0.5, rely=0.5, anchor='center')

        # ── Grid scrollável (aparece depois do load) ──────────────────────────
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=C['bg'],
            scrollbar_button_color=C['scrollbar'],
            scrollbar_button_hover_color='#253D50'
        )

        # ── Status bar (bottom) ───────────────────────────────────────────────
        self.status_bar = ctk.CTkLabel(
            self,
            text='Aguardando Valorant...',
            font=ctk.CTkFont(size=11),
            text_color=C['text_dim']
        )
        self.status_bar.pack(side='bottom', pady=7)

        bottom_sep = ctk.CTkFrame(self, fg_color=C['border'], height=1, corner_radius=0)
        bottom_sep.pack(side='bottom', fill='x')

    # ══════════════════════════════════════════════════════════════════════════
    # Agent Grid
    # ══════════════════════════════════════════════════════════════════════════

    def _start_agent_load(self):
        self._set_status('⏳ Baixando dados dos agentes. Aguarde...')
        threading.Thread(target=self._agent_load_thread, daemon=True).start()

    def _agent_load_thread(self):
        agents = fetch_agents(AGENTS_DIR)
        if agents:
            self.after(0, lambda: self._render_agents(agents))
        else:
            self.after(0, lambda: self._set_status(
                '❌ Falha ao carregar agentes. Verifique sua conexão com a internet.'
            ))

    def _render_agents(self, agents):
        self.loading_frame.pack_forget()
        self.scroll.pack(fill='both', expand=True, padx=6, pady=4)

        COLS = 5
        for c in range(COLS):
            self.scroll.columnconfigure(c, weight=1)

        for idx, agent in enumerate(agents):
            row, col = divmod(idx, COLS)
            self._make_card(agent, row, col)

        self._set_status(
            '✅ Agentes carregados!  Selecione um agente e pressione '
            f'{self.hotkey_str} para ativar o instalock.'
        )

    def _make_card(self, agent: dict, row: int, col: int):
        uuid      = agent['uuid']
        is_sel    = uuid == self.selected_agent_id

        card = ctk.CTkFrame(
            self.scroll,
            fg_color=C['bg_card_sel'] if is_sel else C['bg_card'],
            corner_radius=10,
            border_width=2,
            border_color=C['border_sel'] if is_sel else C['border'],
            cursor='hand2'
        )
        card.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')

        # Ícone
        img_path = os.path.join(AGENTS_DIR, f"{uuid}.png")
        if os.path.exists(img_path):
            try:
                pil = Image.open(img_path).resize((88, 88), Image.LANCZOS)
                ctk_img = ctk.CTkImage(pil, size=(88, 88))
                self.agent_imgs[uuid] = ctk_img  # evita GC
                img_lbl = ctk.CTkLabel(card, image=ctk_img, text='')
                img_lbl.pack(pady=(10, 3))
            except Exception:
                ctk.CTkLabel(card, text='?', font=ctk.CTkFont(size=28),
                             text_color=C['text_dim']).pack(pady=(10, 3))
        else:
            ctk.CTkLabel(card, text='?', font=ctk.CTkFont(size=28),
                         text_color=C['text_dim']).pack(pady=(10, 3))

        # Nome
        name_lbl = ctk.CTkLabel(
            card,
            text=agent['displayName'],
            font=ctk.CTkFont(size=11, weight='bold'),
            text_color=C['text'] if is_sel else C['text_mid'],
            wraplength=110
        )
        name_lbl.pack(pady=(0, 4))

        # Role (ex: Duelista)
        if agent.get('role'):
            ctk.CTkLabel(
                card,
                text=agent['role'].upper(),
                font=ctk.CTkFont(size=9),
                text_color=C['accent'] if is_sel else C['text_dim']
            ).pack(pady=(0, 8))
        else:
            ctk.CTkFrame(card, fg_color='transparent', height=8).pack()

        # Click binding
        def handler(e=None, aid=uuid, aname=agent['displayName']):
            self._select_agent(aid, aname)

        card.bind('<Button-1>', handler)
        for child in card.winfo_children():
            child.bind('<Button-1>', handler)

        self.agent_cards[uuid] = (card, name_lbl)

    def _select_agent(self, agent_id: str, agent_name: str):
        # Deseleciona anterior
        if self.selected_agent_id and self.selected_agent_id in self.agent_cards:
            old_card, old_lbl = self.agent_cards[self.selected_agent_id]
            old_card.configure(fg_color=C['bg_card'], border_color=C['border'])
            old_lbl.configure(text_color=C['text_mid'])
            # Também muda a role label se existir
            for w in old_card.winfo_children():
                if isinstance(w, ctk.CTkLabel) and w.cget('text') not in ('', '?'):
                    txt = w.cget('text')
                    if txt == txt.upper() and len(txt) < 30:  # é a role label
                        w.configure(text_color=C['text_dim'])

        # Seleciona novo
        self.selected_agent_id   = agent_id
        self.selected_agent_name = agent_name

        if agent_id in self.agent_cards:
            card, lbl = self.agent_cards[agent_id]
            card.configure(fg_color=C['bg_card_sel'], border_color=C['border_sel'])
            lbl.configure(text_color=C['text'])
            for w in card.winfo_children():
                if isinstance(w, ctk.CTkLabel) and w.cget('text') not in ('', '?'):
                    txt = w.cget('text')
                    if txt == txt.upper() and len(txt) < 30:
                        w.configure(text_color=C['accent'])

        self.agent_lbl.configure(text=agent_name, text_color=C['accent'])

        # Salva
        self.cfg['agent_id']   = agent_id
        self.cfg['agent_name'] = agent_name
        save_config(self.cfg)
        self._set_status(f'✅ {agent_name} definido como agente principal.')

    # ══════════════════════════════════════════════════════════════════════════
    # Hotkey (pynput — global, sem admin)
    # ══════════════════════════════════════════════════════════════════════════

    def _start_kb_listener(self):
        self._hk_mods, self._hk_trigger = parse_hotkey(self.hotkey_str)
        self._pressed_keys.clear()

        if self._kb_listener:
            try:
                self._kb_listener.stop()
            except Exception:
                pass

        self._kb_listener = pynput_kb.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self._kb_listener.start()

    def _on_key_press(self, key):
        self._pressed_keys.add(key)
        self._check_hotkey()

    def _on_key_release(self, key):
        self._pressed_keys.discard(key)

    def _check_hotkey(self):
        """Verifica se a combinação atual bate com a hotkey configurada."""
        if self._hk_trigger is None:
            return

        # Verifica se o trigger está pressionado
        trigger_hit = self._hk_trigger in self._pressed_keys
        if not trigger_hit:
            # Tenta comparar por valor de char
            for k in self._pressed_keys:
                if hasattr(k, 'char') and hasattr(self._hk_trigger, 'char'):
                    if k.char == self._hk_trigger.char:
                        trigger_hit = True
                        break

        if not trigger_hit:
            return

        # Verifica modificadores
        pressed_mods = set()
        for k in self._pressed_keys:
            if k in (pynput_kb.Key.ctrl_l, pynput_kb.Key.ctrl_r, pynput_kb.Key.ctrl):
                pressed_mods.add(pynput_kb.Key.ctrl)
            elif k in (pynput_kb.Key.shift_l, pynput_kb.Key.shift_r, pynput_kb.Key.shift):
                pressed_mods.add(pynput_kb.Key.shift)
            elif k in (pynput_kb.Key.alt_l, pynput_kb.Key.alt_r, pynput_kb.Key.alt_gr, pynput_kb.Key.alt):
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
            self._set_status(
                f'🟢 Instalock ATIVO ({self.selected_agent_name or "sem agente"}).  '
                f'Aguardando fase de seleção...'
            )
        else:
            self.badge_frame.configure(fg_color=C['accent'])
            self.badge_lbl.configure(text='● INATIVO')
            self._set_status('🔴 Instalock desativado.')

    def _change_hotkey(self):
        dialog = ctk.CTkInputDialog(
            text='Digite a nova hotkey:\n(ex: F1, F2, F3, ctrl+shift+l)',
            title='Alterar Hotkey'
        )
        val = dialog.get_input()
        if val and val.strip():
            self.hotkey_str = val.strip()
            self.hotkey_btn.configure(text=f'🔑  {self.hotkey_str}')
            self.hint_lbl.configure(
                text=f'Pressione {self.hotkey_str} para ativar  ·  Clique num agente para selecionar'
            )
            self.cfg['hotkey'] = self.hotkey_str
            save_config(self.cfg)
            self._start_kb_listener()
            self._set_status(f'✅ Hotkey alterada para: {self.hotkey_str}')

    # ══════════════════════════════════════════════════════════════════════════
    # Polling loop (thread separada)
    # ══════════════════════════════════════════════════════════════════════════

    def _start_polling(self):
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _poll_loop(self):
        client        = None
        client_time   = 0
        VALID_REFRESH = 45 * 60   # renova client a cada 45 min
        RETRY_DELAY   = 10        # tenta reconectar a cada 10s

        while True:
            now     = time.time()
            elapsed = now - client_time
            need_refresh = (
                (client is None     and elapsed > RETRY_DELAY) or
                (client is not None and elapsed > VALID_REFRESH)
            )

            if need_refresh:
                try:
                    client      = get_client()
                    client_time = now
                    region      = get_region().upper()
                    self.after(0, lambda r=region: self._set_status(
                        f'✅ Conectado | Região: {r} | F1 para ativar instalock'
                    ))
                except FileNotFoundError:
                    client      = None
                    client_time = now
                    self.after(0, lambda: self._set_status(
                        '⚠️ Valorant não detectado. Abra o jogo e aguarde o menu principal...'
                    ))
                except Exception as e:
                    client      = None
                    client_time = now
                    err = str(e)[:80]
                    self.after(0, lambda msg=err: self._set_status(f'❌ Conexão: {msg}'))

            # ── Polling de pregame ──────────────────────────────────────────
            if self.is_active and self.selected_agent_id and client:
                try:
                    match_id = get_pregame_match_id(client)

                    if match_id and match_id != self.last_match:
                        self.last_match = match_id
                        self.lock_fired = False
                    elif not match_id and self.last_match:
                        self.last_match = None
                        self.lock_fired = False

                    if match_id and not self.lock_fired:
                        name = self.selected_agent_name
                        self.after(0, lambda: self._set_status(
                            '🎯 Agent select detectado! Executando instalock...'
                        ))
                        select_agent(client, self.selected_agent_id)
                        time.sleep(0.05)
                        ok = lock_agent(client, self.selected_agent_id)
                        self.lock_fired = True
                        client_time = 0  # força refresh após lock

                        if ok:
                            self.after(0, lambda n=name: self._set_status(
                                f'🔒 {n} travado com sucesso! GG 🎉'
                            ))
                        else:
                            self.after(0, lambda n=name: self._set_status(
                                f'⚠️ Select OK, mas lock falhou — agente desbloqueado?'
                            ))

                except Exception as e:
                    err = str(e)
                    if any(x in err.lower() for x in ['401', '403', 'unauthorized', 'token', 'lockfile']):
                        client      = None
                        client_time = 0
                    elif 'pre-game' not in err.lower() and 'pregame' not in err.lower():
                        self.after(0, lambda msg=err[:70]: self._set_status(f'❌ {msg}'))

            time.sleep(0.15)

    def _run_diagnostic(self):
        """Testa conexão com a API do Valorant e exibe resultado."""
        self._set_status('🔍 Testando conexão com o Valorant...')

        def do_test():
            r = test_connection()
            lines = []
            if r['error']:
                lines.append(f"❌ ERRO: {r['error']}")
            else:
                log_ok = "✅" if r['log_exists'] else "⚠️"
                lines.append(f"{log_ok} ShooterGame.log: {'encontrado' if r['log_exists'] else 'NÃO encontrado'}")
                lines.append(f"   {r['log_path']}")

                lines.append(f"🌍 Região detectada: {str(r['region']).upper()}")

                ok = "✅" if r['client_ok'] else "❌"
                lines.append(f"{ok} Valclient ativado")

                if r['puuid']:
                    lines.append(f"✅ PUUID: {str(r['puuid'])[:28]}...")
                else:
                    lines.append("❌ PUUID não obtido")

                ok = "✅" if r['presence_ok'] else "❌"
                lines.append(f"{ok} Presence data: {r['session_state'] or 'N/A'}")

                if r['in_pregame']:
                    lines.append("🎯 EM AGENT SELECT! Instalock vai funcionar!")
                    lines.append(f"   Match ID: {str(r['match_id'])[:40]}")
                else:
                    lines.append("ℹ️ Fora de agent select — teste durante a seleção")

            self.after(0, lambda: self._show_diag_dialog(lines))
            self.after(0, lambda: self._set_status(lines[0]))

        threading.Thread(target=do_test, daemon=True).start()

    def _show_diag_dialog(self, lines):
        """Exibe janela com resultado do diagnóstico."""
        win = ctk.CTkToplevel(self)
        win.title("Diagnóstico de Conexão")
        win.geometry("580x420")
        win.configure(fg_color=C['bg'])
        win.grab_set()

        ctk.CTkLabel(
            win, text="🔍 Resultado do Diagnóstico",
            font=ctk.CTkFont(size=15, weight='bold'),
            text_color=C['text']
        ).pack(pady=(20, 10))

        frame = ctk.CTkFrame(win, fg_color=C['bg_card'], corner_radius=10)
        frame.pack(fill='x', padx=20, pady=5)

        for line in lines:
            color = C['accent'] if line.startswith('❌') else (
                    '#00C853' if line.startswith('✅') else C['text_mid'])
            ctk.CTkLabel(
                frame, text=line,
                font=ctk.CTkFont(size=11),
                text_color=color,
                anchor='w',
                wraplength=500,
                justify='left'
            ).pack(anchor='w', padx=15, pady=3)

        ctk.CTkButton(
            win, text="Fechar",
            fg_color=C['accent'], hover_color=C['accent_dim'],
            command=win.destroy,
            width=100
        ).pack(pady=15)

    # ══════════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _set_status(self, msg: str):
        """Atualiza a status bar (thread-safe via after())."""
        self.status_bar.configure(text=msg)

    def _on_close(self):
        """Garante que o listener de teclado pare antes de fechar."""
        if self._kb_listener:
            try:
                self._kb_listener.stop()
            except Exception:
                pass
        self.destroy()


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app = InstalockApp()
    app.mainloop()