import customtkinter as ctk

from core.logger import YDLLogger
from ui.mixins.player_mixin import PlayerMixin
from ui.mixins.converter_mixin import ConverterMixin
from ui.mixins.downloader_mixin import DownloaderMixin
from tkinter import filedialog, messagebox
import yt_dlp
from yt_dlp.utils import DownloadCancelled, sanitize_filename
import threading
import ctypes
import queue
import os
import re
import sys
import subprocess
import json
import shutil
import ssl
import time
import zipfile
import urllib.request
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from datetime import datetime

# Player de áudio (pygame) - opcional
try:
    import pygame
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except Exception:
    PYGAME_AVAILABLE = False

from core.config import (
    CONFIG_FILE, HISTORY_FILE, FFMPEG_URL, FFMPEG_EXE, FFMPEG_DIR, MAX_HISTORY_RENDER, ANSI_RE,
    C_BG, C_TOPBAR, C_SIDEBAR, C_PANEL, C_CARD, C_SURFACE, C_BORDER, C_BORDER_SOFT, C_INPUT_BG,
    C_TEXT, C_MUTED, C_FAINT, C_TRACK, C_HOVER, C_ACCENT, C_ACCENT_HOVER, C_ACCENT_SOFT, C_ACCENT_DIM,
    C_DANGER, C_DANGER_HOVER, C_SUCCESS, C_WHITE, C_ICON, C_ICON_ACTIVE, C_SEG_BG, C_SEG_SEL,
    BTN_DOWNLOAD, BTN_CANCEL, CONV_FORMATS, MEDIA_EXTS, VIDEO_EXTS, VIDEO_QUALITIES, AUDIO_QUALITIES,
    load_config, save_config, load_history, save_history, url_key, fmt_duration, app_dir, find_ffmpeg
)
# ==================== SELEÇÃO DE ITENS DA PLAYLIST ====================
class PlaylistSelector(ctk.CTkToplevel):
    """Janela para escolher quais músicas/vídeos de uma playlist serão baixados."""

    def __init__(self, parent, playlist_title, entries, preselect=None):
        super().__init__(parent)
        self.title("Selecionar itens da playlist")
        self.geometry("700x620")
        self.minsize(540, 420)
        self.configure(fg_color=C_BG)
        self.result = None
        self.entries = entries
        self.rows = []
        self.filter_term = ""

        self.transient(parent)
        self.grab_set()

        # --- Cabeçalho ---
        title = playlist_title or "Playlist"
        title = title if len(title) <= 70 else title[:67] + "..."
        head = ctk.CTkFrame(self, corner_radius=12, fg_color=C_PANEL,
                            border_width=1, border_color=C_BORDER)
        head.pack(fill="x", padx=16, pady=(16, 10))

        head_inner = ctk.CTkFrame(head, fg_color="transparent")
        head_inner.pack(fill="x", padx=18, pady=16)

        ctk.CTkLabel(
            head_inner, text="PLAYLIST",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=C_ACCENT, anchor="w"
        ).pack(fill="x")
        ctk.CTkLabel(
            head_inner, text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=C_TEXT, anchor="w"
        ).pack(fill="x", pady=(3, 0))
        ctk.CTkLabel(
            head_inner, text=f"{len(entries)} itens encontrados · marque o que deseja baixar",
            font=ctk.CTkFont(size=12),
            text_color=C_MUTED, anchor="w"
        ).pack(fill="x", pady=(3, 0))

        # --- Ferramentas (filtro + marcar/desmarcar) ---
        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=16, pady=(0, 10))

        self.search_entry = ctk.CTkEntry(
            tools, placeholder_text="Filtrar por nome...", width=240, height=34,
            corner_radius=9, border_width=1, border_color=C_BORDER,
            fg_color=C_CARD, text_color=C_TEXT, placeholder_text_color=C_FAINT,
            font=ctk.CTkFont(size=13)
        )
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", self.apply_filter)

        ctk.CTkButton(
            tools, text="Desmarcar", width=98, height=34, corner_radius=9,
            fg_color="transparent", border_width=1, border_color=C_BORDER,
            text_color=C_TEXT, hover_color=C_HOVER,
            font=ctk.CTkFont(size=12), command=self.select_none
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            tools, text="Marcar todos", width=108, height=34, corner_radius=9,
            fg_color="transparent", border_width=1, border_color=C_BORDER,
            text_color=C_TEXT, hover_color=C_HOVER,
            font=ctk.CTkFont(size=12), command=self.select_all
        ).pack(side="right")

        # --- Lista ---
        self.scroll = ctk.CTkScrollableFrame(
            self, corner_radius=10, fg_color=C_SURFACE,
            border_width=1, border_color=C_BORDER,
            scrollbar_fg_color=C_SURFACE,
            scrollbar_button_color=C_BORDER,
            scrollbar_button_hover_color=C_MUTED
        )
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        for index, entry in enumerate(entries, 1):
            self._add_row(index, entry, preselect)

        # --- Rodapé ---
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 14))

        self.count_label = ctk.CTkLabel(
            footer, text="", font=ctk.CTkFont(size=12),
            text_color=C_MUTED
        )
        self.count_label.pack(side="left")

        ctk.CTkButton(
            footer, text="Cancelar", width=110, height=40, corner_radius=10,
            fg_color="transparent", border_width=1, border_color=C_BORDER,
            text_color=C_TEXT, hover_color=C_HOVER,
            font=ctk.CTkFont(size=13), command=self.on_cancel
        ).pack(side="right", padx=(10, 0))

        self.download_btn = ctk.CTkButton(
            footer, text=BTN_DOWNLOAD, height=40, corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER,
            text_color=C_WHITE, text_color_disabled=C_WHITE,
            command=self.on_confirm
        )
        self.download_btn.pack(side="right")

        self.update_count()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.bind("<Escape>", lambda _event: self.on_cancel())

        # Centraliza na janela principal
        self.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    def _add_row(self, index, entry, preselect):
        row = ctk.CTkFrame(self.scroll, corner_radius=8, fg_color=C_CARD,
                           border_width=1, border_color=C_BORDER_SOFT)
        title = entry.get("title") or entry.get("id") or "Sem título"
        title = title if len(title) <= 70 else title[:67] + "..."
        duration = fmt_duration(entry.get("duration"))
        text = f"{index}.  {title}" + (f"   ({duration})" if duration else "")

        checked = True
        if preselect is not None:
            checked = url_key(entry.get("webpage_url") or entry.get("url")) in preselect

        checkbox = ctk.CTkCheckBox(
            row, text=text, font=ctk.CTkFont(size=13),
            text_color=C_TEXT, fg_color=C_ACCENT,
            border_color=C_BORDER, border_width=1, hover_color=C_ACCENT_HOVER,
            command=self.update_count, checkbox_width=20, checkbox_height=20
        )
        if checked:
            checkbox.select()
        else:
            checkbox.deselect()
        checkbox.pack(fill="x", padx=14, pady=11)

        row.pack(fill="x", padx=8, pady=4)
        self.rows.append((row, checkbox, entry))

    # --- Ações ---
    def apply_filter(self, _event=None):
        self.filter_term = self.search_entry.get().strip().lower()
        for row, _checkbox, entry in self.rows:
            show = not self.filter_term or self.filter_term in (entry.get("title") or "").lower()
            if show:
                row.pack(fill="x", padx=6, pady=3)
            else:
                row.pack_forget()
        self.update_count()

    def select_all(self):
        for _row, checkbox, _entry in self.rows:
            checkbox.select()
        self.update_count()

    def select_none(self):
        for _row, checkbox, _entry in self.rows:
            checkbox.deselect()
        self.update_count()

    def update_count(self):
        total = len(self.rows)
        selected = sum(1 for _row, checkbox, _entry in self.rows if checkbox.get())
        self.count_label.configure(text=f"{selected} de {total} selecionados")
        if selected:
            self.download_btn.configure(
                state="normal", text=f"Baixar ({selected})",
                fg_color=C_ACCENT
            )
        else:
            self.download_btn.configure(
                state="disabled", text=BTN_DOWNLOAD,
                fg_color=C_ACCENT_DIM
            )

    def on_confirm(self):
        selected = [entry for _row, checkbox, entry in self.rows if checkbox.get()]
        if not selected:
            messagebox.showwarning("Aviso", "Marque pelo menos um item.", parent=self)
            return
        self.result = selected
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()


# ==================== APLICATIVO ====================
class LDYouTubeDownloader(ctk.CTk, PlayerMixin, ConverterMixin, DownloaderMixin):
    def __init__(self):
        super().__init__()

        self.title("LD Youtube Downloader")
        self.geometry("900x700")
        self.minsize(760, 580)

        # Tema Escuro Profissional
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.app_config = load_config()
        self.history = load_history()
        self.download_path = self.app_config.get("last_dir", str(Path.home() / "Downloads"))
        self.ffmpeg_location = find_ffmpeg(self.app_config)

        self.is_downloading = False
        self.cancel_event = threading.Event()
        self.current_file = None
        self.overwrite = False
        self._mode = "video"
        self._quality = VIDEO_QUALITIES[0]
        self._target_dir = self.download_path
        self._pending_items = None
        self._last_hook_ui = 0.0
        self._last_url = ""
        self._download_started = False
        self.history_widgets = []
        self._ui_queue = queue.Queue()

        # Player state
        self._player_state = "stopped"
        self._player_file = None
        self._player_duration = 0.0
        self._lib_file_items = []

        # Converter state
        self._converter_files = []
        self._conv_file_widgets = []  # [(widget, filepath, status_label)]

        # Sidebar state
        self._panels = {}
        self._sidebar_btns = {}

        self.create_widgets()
        self.update_path_label()
        self.render_history()

        self.center_on_screen()

        # entrega de callbacks vindos das threads (fila de segurança)
        self.after(50, self._drain_ui)

    def center_on_screen(self):
        """Centraliza a janela na tela.

        Em telas HiDPI o Tk pode reportar o tamanho da tela desatualizado
        (winfo_screenwidth), então preferimos o GetSystemMetrics do Windows.
        """
        self.update()  # mapeia a janela para obter o tamanho real
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        if sys.platform == "win32":
            try:
                screen_w = ctypes.windll.user32.GetSystemMetrics(0)
                screen_h = ctypes.windll.user32.GetSystemMetrics(1)
            except Exception:
                pass
        x = max(0, (screen_w - self.winfo_width()) // 2)
        y = max(0, (screen_h - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    # ==================== LAYOUT PRINCIPAL ====================
    def create_widgets(self):
        self.configure(fg_color=C_BG)

        # ===== TOPBAR =====
        topbar = ctk.CTkFrame(self, corner_radius=0, fg_color=C_TOPBAR, height=48)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        ctk.CTkLabel(topbar, text="LD Youtube Downloader",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color=C_TEXT).pack(side="left", expand=True)
        ctk.CTkLabel(topbar, text="MP3 · MP4 · Playlists",
                     font=ctk.CTkFont(size=10), text_color=C_FAINT, width=140).pack(side="right")
        ctk.CTkFrame(self, height=1, fg_color=C_BORDER, corner_radius=0).pack(fill="x")

        # ===== BODY (sidebar + conteúdo) =====
        body = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        body.pack(fill="both", expand=True)
        self._create_sidebar(body)

        self._content_frame = ctk.CTkFrame(body, fg_color=C_PANEL, corner_radius=0)
        self._content_frame.pack(side="left", fill="both", expand=True)

        # Cria todos os painéis
        self._panels["downloads"] = self._create_downloads_panel(self._content_frame)
        self._panels["library"]   = self._create_library_panel(self._content_frame)
        self._panels["converter"] = self._create_converter_panel(self._content_frame)

        # ===== STATUSBAR =====
        statusbar = ctk.CTkFrame(self, corner_radius=0, fg_color=C_TOPBAR, height=26)
        statusbar.pack(fill="x", side="bottom")
        statusbar.pack_propagate(False)
        self.status_label = ctk.CTkLabel(statusbar, text="Pronto para baixar",
                                          font=ctk.CTkFont(size=10), text_color=C_MUTED, anchor="w")
        self.status_label.pack(side="left", padx=16, fill="y")
        ctk.CTkLabel(statusbar, text="LD Youtube Downloader  ·  v2.0",
                     font=ctk.CTkFont(size=10), text_color=C_FAINT, anchor="e").pack(side="right", padx=16, fill="y")

        # Mostra painel padrão
        self._switch_panel("downloads")

    # ==================== SIDEBAR ====================
    def _create_sidebar(self, body):
        sidebar = ctk.CTkFrame(body, corner_radius=0, fg_color=C_SIDEBAR, width=72)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        def make_btn(symbol, label, panel_name):
            container = ctk.CTkFrame(sidebar, fg_color="transparent", corner_radius=0, cursor="hand2")
            container.pack(fill="x")
            icon_lbl = ctk.CTkLabel(container, text=symbol, font=ctk.CTkFont(size=22),
                                     text_color=C_ICON)
            icon_lbl.pack(pady=(12, 2))
            text_lbl = ctk.CTkLabel(container, text=label, font=ctk.CTkFont(size=9),
                                     text_color=C_ICON, wraplength=68, justify="center")
            text_lbl.pack(pady=(0, 8))
            indicator = ctk.CTkFrame(sidebar, height=2, fg_color="transparent", corner_radius=0)
            indicator.pack(fill="x")

            def on_click(e=None, pn=panel_name):
                self._switch_panel(pn)
            for w in (container, icon_lbl, text_lbl):
                w.bind("<Button-1>", on_click)

            self._sidebar_btns[panel_name] = (icon_lbl, text_lbl, indicator)

        make_btn("⬇", "Downloads", "downloads")
        make_btn("📚", "Biblioteca", "library")
        make_btn("🔄", "Converter", "converter")

    def _switch_panel(self, name):
        for pn, (icon, txt, ind) in self._sidebar_btns.items():
            if pn == name:
                icon.configure(text_color=C_ACCENT)
                txt.configure(text_color=C_ACCENT)
                ind.configure(fg_color=C_ACCENT)
            else:
                icon.configure(text_color=C_ICON)
                txt.configure(text_color=C_ICON)
                ind.configure(fg_color="transparent")
        for pn, panel in self._panels.items():
            if pn == name:
                panel.pack(fill="both", expand=True)
            else:
                panel.pack_forget()

    # ==================== PAINEL: DOWNLOADS ====================
    def _create_downloads_panel(self, parent):
        panel = ctk.CTkFrame(parent, corner_radius=0, fg_color=C_PANEL)

        # URL bar
        url_bar = ctk.CTkFrame(panel, corner_radius=0, fg_color=C_TOPBAR, height=56)
        url_bar.pack(fill="x")
        url_bar.pack_propagate(False)
        url_inner = ctk.CTkFrame(url_bar, fg_color="transparent")
        url_inner.pack(fill="both", expand=True, padx=16, pady=8)
        ctk.CTkLabel(url_inner, text="🌐", font=ctk.CTkFont(size=14),
                     text_color=C_FAINT, width=28).pack(side="left")
        self.url_entry = ctk.CTkEntry(url_inner,
            placeholder_text="Insira o link do vídeo ou playlist...",
            height=36, corner_radius=0, border_width=0,
            fg_color="transparent", text_color=C_TEXT,
            placeholder_text_color=C_FAINT, font=ctk.CTkFont(size=13))
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(4, 10))
        self.url_entry.bind("<Return>", lambda _: self.start_download())
        self.download_btn = ctk.CTkButton(url_inner, text=BTN_DOWNLOAD,
            width=130, height=36, corner_radius=6,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER,
            text_color=C_WHITE, text_color_disabled=C_WHITE,
            font=ctk.CTkFont(size=13, weight="bold"), command=self.start_download)
        self.download_btn.pack(side="right")

        ctk.CTkFrame(panel, height=1, fg_color=C_BORDER, corner_radius=0).pack(fill="x")

        # Opções bar
        opts_bar = ctk.CTkFrame(panel, corner_radius=0, fg_color=C_TOPBAR, height=44)
        opts_bar.pack(fill="x")
        opts_bar.pack_propagate(False)
        opts_inner = ctk.CTkFrame(opts_bar, fg_color="transparent")
        opts_inner.pack(fill="both", expand=True, padx=16)
        ctk.CTkLabel(opts_inner, text="Formato:", font=ctk.CTkFont(size=11),
                     text_color=C_MUTED).pack(side="left", padx=(0, 8))

        self.download_type = ctk.StringVar(value="video")
        self.mode_label = ctk.StringVar(value="Vídeo")
        self._quality_choice = {"video": VIDEO_QUALITIES[0], "audio": AUDIO_QUALITIES[0]}
        self.segment = ctk.CTkSegmentedButton(
            opts_inner, values=["Vídeo", "Áudio (MP3)"],
            variable=self.mode_label, command=self._on_mode_change,
            height=28, corner_radius=5, font=ctk.CTkFont(size=11),
            fg_color=C_SEG_BG, selected_color=C_ACCENT,
            selected_hover_color=C_ACCENT_HOVER, unselected_color=C_SEG_BG,
            unselected_hover_color=C_HOVER, text_color=C_TEXT, border_width=2)
        self.segment.pack(side="left")
        ctk.CTkLabel(opts_inner, text="Qualidade:", font=ctk.CTkFont(size=11),
                     text_color=C_MUTED).pack(side="left", padx=(20, 8))
        self.quality_menu = ctk.CTkOptionMenu(
            opts_inner, values=VIDEO_QUALITIES, width=140, height=28, corner_radius=5,
            command=self._on_quality_change, fg_color=C_SEG_BG,
            button_color=C_BORDER, button_hover_color=C_HOVER, text_color=C_TEXT,
            font=ctk.CTkFont(size=11), dropdown_font=ctk.CTkFont(size=11),
            dropdown_fg_color=C_CARD, dropdown_hover_color=C_HOVER, dropdown_text_color=C_TEXT)
        self.quality_menu.set(VIDEO_QUALITIES[0])
        self.quality_menu.pack(side="left")
        self.cancel_btn = ctk.CTkButton(
            opts_inner, text="✕  Cancelar", width=100, height=28, corner_radius=5,
            fg_color="transparent", border_width=1, border_color=C_BORDER,
            text_color=C_DANGER, text_color_disabled=C_FAINT,
            hover_color=C_DANGER_HOVER, font=ctk.CTkFont(size=11),
            state="disabled", command=self.cancel_download)
        self.cancel_btn.pack(side="right")

        ctk.CTkFrame(panel, height=1, fg_color=C_BORDER, corner_radius=0).pack(fill="x")

        # Pasta de destino
        path_bar = ctk.CTkFrame(panel, corner_radius=0, fg_color=C_BG, height=34)
        path_bar.pack(fill="x")
        path_bar.pack_propagate(False)
        path_inner = ctk.CTkFrame(path_bar, fg_color="transparent")
        path_inner.pack(fill="both", expand=True, padx=16)
        ctk.CTkLabel(path_inner, text="📁", font=ctk.CTkFont(size=12), text_color=C_FAINT).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(path_inner, text="Salvar em:", font=ctk.CTkFont(size=11),
                     text_color=C_MUTED).pack(side="left", padx=(0, 8))
        self.path_label = ctk.CTkLabel(path_inner, text="", font=ctk.CTkFont(size=11),
                                        text_color=C_ACCENT, anchor="w", cursor="hand2")
        self.path_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(path_inner, text="Alterar", width=70, height=22, corner_radius=4,
                      fg_color="transparent", border_width=1, border_color=C_BORDER,
                      text_color=C_MUTED, hover_color=C_HOVER, font=ctk.CTkFont(size=10),
                      command=self.choose_directory).pack(side="right")

        ctk.CTkFrame(panel, height=1, fg_color=C_BORDER, corner_radius=0).pack(fill="x")

        # Progresso
        self.progress = ctk.CTkProgressBar(panel, height=3, corner_radius=0,
                                            fg_color=C_BORDER, progress_color=C_ACCENT)
        self.progress.pack(fill="x")
        self.progress.set(0)

        # Cabeçalho do histórico
        hist_header = ctk.CTkFrame(panel, corner_radius=0, fg_color=C_BG, height=38)
        hist_header.pack(fill="x")
        hist_header.pack_propagate(False)
        hist_inner = ctk.CTkFrame(hist_header, fg_color="transparent")
        hist_inner.pack(fill="both", expand=True, padx=16)
        self.history_title = ctk.CTkLabel(hist_inner, text="Downloads recentes",
                                           font=ctk.CTkFont(size=11, weight="bold"), text_color=C_MUTED)
        self.history_title.pack(side="left")
        self.history_hint = ctk.CTkLabel(hist_inner, text="", font=ctk.CTkFont(size=10), text_color=C_FAINT)
        self.history_hint.pack(side="left", padx=(10, 0))
        ctk.CTkButton(hist_inner, text="Limpar", width=58, height=22, corner_radius=4,
                      fg_color="transparent", border_width=1, border_color=C_BORDER,
                      text_color=C_FAINT, hover_color=C_HOVER, font=ctk.CTkFont(size=10),
                      command=self.clear_history).pack(side="right")

        self.history_frame = ctk.CTkScrollableFrame(
            panel, corner_radius=0, fg_color=C_SURFACE, border_width=0,
            scrollbar_fg_color=C_SURFACE, scrollbar_button_color=C_BORDER,
            scrollbar_button_hover_color=C_MUTED)
        self.history_frame.pack(fill="both", expand=True)
        self.empty_label = ctk.CTkLabel(self.history_frame, text="Nenhum download ainda.",
                                         font=ctk.CTkFont(size=12), text_color=C_FAINT)
        if not self.history:
            self.empty_label.pack(pady=40)

        return panel

    # ==================== PAINEL: BIBLIOTECA + PLAYER ====================
    def _create_library_panel(self, parent):
        panel = ctk.CTkFrame(parent, corner_radius=0, fg_color=C_PANEL)

        # Header
        hdr = ctk.CTkFrame(panel, corner_radius=0, fg_color=C_TOPBAR, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        hi = ctk.CTkFrame(hdr, fg_color="transparent")
        hi.pack(fill="both", expand=True, padx=16)
        ctk.CTkLabel(hi, text="Biblioteca de Mídia", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C_TEXT).pack(side="left")
        ctk.CTkButton(hi, text="📂 Abrir pasta", width=110, height=28, corner_radius=5,
                      fg_color="transparent", border_width=1, border_color=C_BORDER,
                      text_color=C_MUTED, hover_color=C_HOVER, font=ctk.CTkFont(size=11),
                      command=self._library_open_folder).pack(side="right")
        ctk.CTkFrame(panel, height=1, fg_color=C_BORDER, corner_radius=0).pack(fill="x")

        # Split: lista (esq) | player (dir)
        body = ctk.CTkFrame(panel, fg_color=C_PANEL, corner_radius=0)
        body.pack(fill="both", expand=True)

        # --- Lista de arquivos ---
        list_col = ctk.CTkFrame(body, fg_color=C_BG, corner_radius=0, width=280)
        list_col.pack(side="left", fill="y")
        list_col.pack_propagate(False)
        lh = ctk.CTkFrame(list_col, fg_color=C_SURFACE, corner_radius=0, height=30)
        lh.pack(fill="x")
        lh.pack_propagate(False)
        ctk.CTkLabel(lh, text="Arquivos", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C_MUTED).pack(side="left", padx=12, fill="y")
        self._lib_list = ctk.CTkScrollableFrame(list_col, corner_radius=0, fg_color=C_BG,
                                                  border_width=0, scrollbar_fg_color=C_BG,
                                                  scrollbar_button_color=C_BORDER,
                                                  scrollbar_button_hover_color=C_MUTED)
        self._lib_list.pack(fill="both", expand=True)
        self._lib_empty = ctk.CTkLabel(self._lib_list,
                                        text="Abra uma pasta com\narquivos de mídia.",
                                        font=ctk.CTkFont(size=12), text_color=C_FAINT, justify="center")
        self._lib_empty.pack(pady=40)

        ctk.CTkFrame(body, width=1, fg_color=C_BORDER, corner_radius=0).pack(side="left", fill="y")

        # --- Player ---
        player_col = ctk.CTkFrame(body, fg_color=C_PANEL, corner_radius=0)
        player_col.pack(side="left", fill="both", expand=True)

        # Área de informações do arquivo
        info_box = ctk.CTkFrame(player_col, fg_color=C_SURFACE, corner_radius=12)
        info_box.pack(fill="x", padx=24, pady=20)
        self._player_type_lbl = ctk.CTkLabel(info_box, text="🎵",
                                               font=ctk.CTkFont(size=52), text_color=C_ACCENT)
        self._player_type_lbl.pack(pady=(24, 8))
        self._player_title_lbl = ctk.CTkLabel(info_box, text="Nenhum arquivo selecionado",
                                               font=ctk.CTkFont(size=14, weight="bold"),
                                               text_color=C_TEXT, wraplength=300, justify="center")
        self._player_title_lbl.pack(padx=24, pady=(0, 4))
        self._player_info_lbl = ctk.CTkLabel(info_box, text="",
                                              font=ctk.CTkFont(size=11), text_color=C_MUTED)
        self._player_info_lbl.pack(pady=(0, 24))

        # Barra de progresso do player
        prog_row = ctk.CTkFrame(player_col, fg_color="transparent")
        prog_row.pack(fill="x", padx=24, pady=(0, 6))
        self._player_time_lbl = ctk.CTkLabel(prog_row, text="0:00",
                                              font=ctk.CTkFont(size=10), text_color=C_FAINT, width=36)
        self._player_time_lbl.pack(side="left")
        self._player_progress = ctk.CTkSlider(
            prog_row, from_=0, to=100, height=14, corner_radius=4,
            button_color=C_ACCENT, button_hover_color=C_ACCENT_HOVER,
            fg_color=C_TRACK, progress_color=C_ACCENT, command=self._player_seek)
        self._player_progress.pack(side="left", fill="x", expand=True, padx=8)
        self._player_progress.set(0)
        self._player_total_lbl = ctk.CTkLabel(prog_row, text="0:00",
                                               font=ctk.CTkFont(size=10), text_color=C_FAINT, width=36)
        self._player_total_lbl.pack(side="right")

        # Controles
        ctrl_row = ctk.CTkFrame(player_col, fg_color="transparent")
        ctrl_row.pack(pady=(0, 12))
        ctk.CTkButton(ctrl_row, text="⏮", width=36, height=36, corner_radius=18,
                      fg_color=C_CARD, hover_color=C_HOVER, text_color=C_MUTED,
                      font=ctk.CTkFont(size=16), command=self._player_prev).pack(side="left", padx=4)
        self._player_play_btn = ctk.CTkButton(
            ctrl_row, text="▶", width=56, height=56, corner_radius=28,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color=C_WHITE,
            font=ctk.CTkFont(size=22), command=self._player_toggle)
        self._player_play_btn.pack(side="left", padx=6)
        ctk.CTkButton(ctrl_row, text="⏭", width=36, height=36, corner_radius=18,
                      fg_color=C_CARD, hover_color=C_HOVER, text_color=C_MUTED,
                      font=ctk.CTkFont(size=16), command=self._player_next).pack(side="left", padx=4)
        ctk.CTkButton(ctrl_row, text="⏹", width=36, height=36, corner_radius=18,
                      fg_color=C_CARD, hover_color=C_HOVER, text_color=C_MUTED,
                      font=ctk.CTkFont(size=14), command=self._player_stop).pack(side="left", padx=4)

        # Volume
        vol_row = ctk.CTkFrame(player_col, fg_color="transparent")
        vol_row.pack(pady=(0, 8))
        ctk.CTkLabel(vol_row, text="🔊", font=ctk.CTkFont(size=13), text_color=C_MUTED).pack(side="left")
        self._player_vol = ctk.CTkSlider(
            vol_row, from_=0, to=1, width=130, height=10,
            button_color=C_ACCENT, button_hover_color=C_ACCENT_HOVER,
            fg_color=C_TRACK, progress_color=C_ACCENT, command=self._player_set_volume)
        self._player_vol.set(0.85)
        self._player_vol.pack(side="left", padx=8)

        ctk.CTkButton(player_col, text="🎬 Abrir com player do sistema",
                      width=220, height=30, corner_radius=5,
                      fg_color="transparent", border_width=1, border_color=C_BORDER,
                      text_color=C_MUTED, hover_color=C_HOVER, font=ctk.CTkFont(size=11),
                      command=self._player_open_system).pack(pady=(0, 8))

        if not PYGAME_AVAILABLE:
            ctk.CTkLabel(player_col,
                         text="⚠ pygame não instalado  —  pip install pygame",
                         font=ctk.CTkFont(size=10), text_color=C_DANGER).pack(pady=(0, 6))

        self._lib_current_idx = -1
        return panel

    # ==================== PAINEL: CONVERSOR ====================
    def _create_converter_panel(self, parent):
        panel = ctk.CTkFrame(parent, corner_radius=0, fg_color=C_PANEL)

        # Header
        hdr = ctk.CTkFrame(panel, corner_radius=0, fg_color=C_TOPBAR, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        hi = ctk.CTkFrame(hdr, fg_color="transparent")
        hi.pack(fill="both", expand=True, padx=16)
        ctk.CTkLabel(hi, text="Conversor de Mídia", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C_TEXT).pack(side="left")
        ctk.CTkFrame(panel, height=1, fg_color=C_BORDER, corner_radius=0).pack(fill="x")

        # Controles
        ctrl = ctk.CTkFrame(panel, corner_radius=0, fg_color=C_BG, height=52)
        ctrl.pack(fill="x")
        ctrl.pack_propagate(False)
        ci = ctk.CTkFrame(ctrl, fg_color="transparent")
        ci.pack(fill="both", expand=True, padx=14, pady=8)

        ctk.CTkButton(ci, text="📄 Arquivos", height=32, corner_radius=5, width=110,
                      fg_color=C_CARD, hover_color=C_HOVER, text_color=C_TEXT,
                      border_width=1, border_color=C_BORDER, font=ctk.CTkFont(size=11),
                      command=self._conv_select_files).pack(side="left", padx=(0, 6))
        ctk.CTkButton(ci, text="📂 Pasta", height=32, corner_radius=5, width=90,
                      fg_color=C_CARD, hover_color=C_HOVER, text_color=C_TEXT,
                      border_width=1, border_color=C_BORDER, font=ctk.CTkFont(size=11),
                      command=self._conv_select_folder).pack(side="left", padx=(0, 16))
        ctk.CTkLabel(ci, text="→", font=ctk.CTkFont(size=13),
                     text_color=C_MUTED).pack(side="left", padx=(0, 8))
        self._conv_format = ctk.CTkOptionMenu(
            ci, values=CONV_FORMATS, width=88, height=32, corner_radius=5,
            fg_color=C_SEG_BG, button_color=C_BORDER, button_hover_color=C_HOVER,
            text_color=C_TEXT, font=ctk.CTkFont(size=11),
            dropdown_font=ctk.CTkFont(size=11), dropdown_fg_color=C_CARD,
            dropdown_hover_color=C_HOVER, dropdown_text_color=C_TEXT)
        self._conv_format.set("MP3")
        self._conv_format.pack(side="left", padx=(0, 12))

        self._conv_delete_orig = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(ci, text="Remover original", variable=self._conv_delete_orig,
                        font=ctk.CTkFont(size=11), text_color=C_MUTED,
                        fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER,
                        border_color=C_BORDER, border_width=1,
                        checkbox_width=16, checkbox_height=16).pack(side="left", padx=(0, 12))

        self._conv_start_btn = ctk.CTkButton(
            ci, text="⚡ Converter", height=32, width=110, corner_radius=5,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER,
            text_color=C_WHITE, font=ctk.CTkFont(size=12, weight="bold"),
            command=self._conv_start)
        self._conv_start_btn.pack(side="right")

        ctk.CTkFrame(panel, height=1, fg_color=C_BORDER, corner_radius=0).pack(fill="x")

        # Cabeçalho da lista
        fh = ctk.CTkFrame(panel, corner_radius=0, fg_color=C_SURFACE, height=30)
        fh.pack(fill="x")
        fh.pack_propagate(False)
        fhi = ctk.CTkFrame(fh, fg_color="transparent")
        fhi.pack(fill="both", expand=True, padx=12)
        ctk.CTkLabel(fhi, text="Arquivos selecionados",
                     font=ctk.CTkFont(size=10, weight="bold"), text_color=C_FAINT).pack(side="left", fill="y")
        self._conv_count_lbl = ctk.CTkLabel(fhi, text="0 arquivos",
                                             font=ctk.CTkFont(size=10), text_color=C_FAINT)
        self._conv_count_lbl.pack(side="right", fill="y")

        # Lista de arquivos
        self._conv_list_frame = ctk.CTkScrollableFrame(
            panel, corner_radius=0, fg_color=C_SURFACE, border_width=0,
            scrollbar_fg_color=C_SURFACE, scrollbar_button_color=C_BORDER,
            scrollbar_button_hover_color=C_MUTED)
        self._conv_list_frame.pack(fill="both", expand=True)
        self._conv_empty_lbl = ctk.CTkLabel(self._conv_list_frame,
                                             text="Selecione arquivos ou uma pasta para converter.",
                                             font=ctk.CTkFont(size=12), text_color=C_FAINT)
        self._conv_empty_lbl.pack(pady=40)

        ctk.CTkFrame(panel, height=1, fg_color=C_BORDER, corner_radius=0).pack(fill="x")

        # Rodapé com progresso
        bot = ctk.CTkFrame(panel, corner_radius=0, fg_color=C_BG, height=54)
        bot.pack(fill="x")
        bot.pack_propagate(False)
        bi = ctk.CTkFrame(bot, fg_color="transparent")
        bi.pack(fill="both", expand=True, padx=16, pady=8)
        self._conv_progress = ctk.CTkProgressBar(bi, height=4, corner_radius=2,
                                                   fg_color=C_BORDER, progress_color=C_ACCENT)
        self._conv_progress.pack(fill="x", pady=(0, 6))
        self._conv_progress.set(0)
        self._conv_status_lbl = ctk.CTkLabel(bi, text="Pronto para converter",
                                              font=ctk.CTkFont(size=11), text_color=C_MUTED, anchor="w")
        self._conv_status_lbl.pack(fill="x")

        self._conv_file_widgets = []
        self._converter_files = []
        return panel

    # ==================== HELPERS DE ESTILO ====================
    @staticmethod
    def caption(parent, text):
        """Rótulo de seção discreto."""
        return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=10, weight="bold"),
                            text_color=C_FAINT, anchor="w")

    def set_download_button(self, text, disabled=False):
        """Atualiza texto/estado do botão principal mantendo o estilo."""
        self.download_btn.configure(
            text=text, state="disabled" if disabled else "normal",
            fg_color=C_ACCENT_DIM if disabled else C_ACCENT)

    # ==================== PLAYER METHODS ====================
    def _library_open_folder(self):
        path = filedialog.askdirectory(initialdir=self.download_path, parent=self)
        if not path:
            return
        files = sorted(
            [f for f in Path(path).iterdir() if f.is_file() and f.suffix.lower() in MEDIA_EXTS],
            key=lambda f: f.name.lower())
        self._library_populate(files)

    def _library_populate(self, files):
        for widget, _ in self._lib_file_items:
            try:
                widget.destroy()
            except Exception:
                pass
        self._lib_file_items = []
        self._lib_current_idx = -1

        try:
            self._lib_empty.destroy()
        except Exception:
            pass

        if not files:
            self._lib_empty = ctk.CTkLabel(self._lib_list,
                                            text="Nenhum arquivo de mídia encontrado.",
                                            font=ctk.CTkFont(size=12), text_color=C_FAINT)
            self._lib_empty.pack(pady=40)
            return

        for fp in files:
            self._lib_add_file_row(fp)

    def _lib_add_file_row(self, filepath):
        ext = filepath.suffix.lower()
        is_video = ext in VIDEO_EXTS
        icon = "🎬" if is_video else "🎵"
        idx = len(self._lib_file_items)

        item = ctk.CTkFrame(self._lib_list, corner_radius=0, fg_color=C_BG, cursor="hand2")
        item.pack(fill="x")
        inner = ctk.CTkFrame(item, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(inner, text=icon, font=ctk.CTkFont(size=13), text_color=C_MUTED,
                     width=22).pack(side="left")
        name = filepath.stem
        name_lbl = ctk.CTkLabel(inner,
                                  text=name[:38] + "..." if len(name) > 38 else name,
                                  font=ctk.CTkFont(size=11), text_color=C_TEXT, anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ctk.CTkFrame(item, height=1, fg_color=C_BORDER_SOFT, corner_radius=0).pack(fill="x")

        self._lib_file_items.append((item, str(filepath)))

        def on_click(e=None, i=idx, fp=str(filepath), it=item):
            for w, _ in self._lib_file_items:
                w.configure(fg_color=C_BG)
            it.configure(fg_color=C_HOVER)
            self._lib_current_idx = i
            self._player_load_and_play(fp)

        item.bind("<Button-1>", on_click)
        inner.bind("<Button-1>", on_click)
        name_lbl.bind("<Button-1>", on_click)

    # ==================== CONVERSOR METHODS ====================
    def _conv_add_file_row(self, filepath):
        ext = Path(filepath).suffix.upper().lstrip(".")
        name = Path(filepath).name
        display = name if len(name) <= 65 else name[:62] + "..."
        item = ctk.CTkFrame(self._conv_list_frame, corner_radius=0, fg_color=C_SURFACE)
        item.pack(fill="x")
        inner = ctk.CTkFrame(item, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(inner, text=ext, font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=C_ACCENT, width=36, height=18,
                     corner_radius=3, fg_color=C_CARD).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(inner, text=display, font=ctk.CTkFont(size=11),
                     text_color=C_TEXT, anchor="w").pack(side="left", fill="x", expand=True)
        status_lbl = ctk.CTkLabel(inner, text="", font=ctk.CTkFont(size=10),
                                   text_color=C_FAINT, width=90)
        status_lbl.pack(side="right")
        ctk.CTkFrame(item, height=1, fg_color=C_BORDER_SOFT, corner_radius=0).pack(fill="x")
        self._conv_file_widgets.append((item, filepath, status_lbl))

    def ui(self, func, *args, **kwargs):
        """Agenda uma função para rodar na thread principal do Tk.

        Chamadas cross-thread ao Tk (self.after vindo de uma thread worker)
        BLOQUEIAM a thread chamadora até a thread principal processar o
        evento - em testes isso custou ~1,1 s por chamada e deixou o download
        a ~550 B/s. Então, vindo de worker, a tarefa vai apenas para a fila
        (_ui_queue), esvaziada pelo _drain_ui que roda na thread principal.
        """
        if threading.current_thread() is threading.main_thread():
            try:
                self.after(0, lambda: func(*args, **kwargs))
                return
            except Exception:
                pass
        try:
            self._ui_queue.put((func, args, kwargs))
        except Exception:
            pass

    def _drain_ui(self):
        """Entrega as tarefas enfileiradas pelo ui() (roda na thread principal)."""
        try:
            while True:
                item = self._ui_queue.get_nowait()
                if len(item) == 3:
                    func, args, kwargs = item
                else:
                    func, args = item
                    kwargs = {}
                try:
                    func(*args, **kwargs)
                except Exception:
                    pass
        except queue.Empty:
            pass
        except Exception:
            pass
        try:
            self.after(50, self._drain_ui)
        except Exception:
            pass

    def set_status(self, text):
        self.status_label.configure(text=text)

    def _on_mode_change(self, value):
        """Chamado pelo segmented button: 'Vídeo' ou 'Áudio (MP3)'."""
        # guarda a qualidade escolhida no modo anterior
        if self.download_type.get() in self._quality_choice:
            self._quality_choice[self.download_type.get()] = self.quality_menu.get()

        audio = "Áudio" in str(value)
        mode = "audio" if audio else "video"
        self.download_type.set(mode)
        self._mode = mode
        self.refresh_quality_menu()
        self._quality = self.quality_menu.get()

    def _on_quality_change(self, value):
        """Mantém a cópia simples da qualidade atualizada (thread-safe)."""
        self._quality = value

    def refresh_quality_menu(self):
        if self.download_type.get() == "audio":
            self.quality_menu.configure(values=list(AUDIO_QUALITIES))
            self.quality_menu.set(
                self._quality_choice["audio"]
                if self._quality_choice["audio"] in AUDIO_QUALITIES else AUDIO_QUALITIES[0]
            )
        else:
            self.quality_menu.configure(values=list(VIDEO_QUALITIES))
            self.quality_menu.set(
                self._quality_choice["video"]
                if self._quality_choice["video"] in VIDEO_QUALITIES else VIDEO_QUALITIES[0]
            )

    def choose_directory(self):
        if self.is_downloading:
            messagebox.showinfo("Aguarde", "Aguarde o download atual terminar para mudar a pasta.", parent=self)
            return
        path = filedialog.askdirectory(initialdir=self.download_path, parent=self)
        if path:
            self.download_path = path
            self.app_config["last_dir"] = path
            save_config(self.app_config)
            self.update_path_label()

    def update_path_label(self):
        path = self.download_path
        display = path if len(path) <= 72 else "..." + path[-69:]
        self.path_label.configure(text=display)

    def open_folder(self, path):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir a pasta:\n{e}", parent=self)

    # ==================== HISTÓRICO ====================
    def update_history_count(self):
        total = len(self.history)
        if total > MAX_HISTORY_RENDER:
            hint = f"mostrando os {MAX_HISTORY_RENDER} mais recentes de {total}"
        else:
            hint = f"{total} item(s)" if total else ""
        self.history_hint.configure(text=hint)

    def render_history(self):
        for widget in self.history_widgets:
            widget.destroy()
        self.history_widgets = []
        for entry in self.history[:MAX_HISTORY_RENDER]:
            widget = self.build_history_widget(entry)
            widget.pack(fill="x", padx=0, pady=0)
            self.history_widgets.append(widget)

        # o rótulo de lista vazia acompanha o estado atual
        if self.history:
            if getattr(self, "empty_label", None) is not None:
                try:
                    self.empty_label.destroy()
                except Exception:
                    pass
                self.empty_label = None
        elif getattr(self, "empty_label", None) is None:
            self.empty_label = ctk.CTkLabel(
                self.history_frame, text="Nenhum download ainda.",
                font=ctk.CTkFont(size=12), text_color=C_FAINT
            )
            self.empty_label.pack(pady=24)

        self.update_history_count()

    def build_history_widget(self, entry):
        # Container do item: linha flat com borda inferior
        item = ctk.CTkFrame(self.history_frame, corner_radius=0,
                            fg_color=C_SURFACE, border_width=0)

        folder = entry.get("folder", self.download_path)
        filepath = entry.get("filepath")
        title = entry.get("title", "Sem título")
        display = title if len(title) <= 65 else title[:62] + "..."
        kind = entry.get("kind", "video")
        badge = "MP3" if kind == "audio" else "MP4"
        badge_color = "#5B8DD9" if kind == "video" else C_ACCENT

        inner = ctk.CTkFrame(item, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=8)

        # Badge colorido de tipo
        badge_lbl = ctk.CTkLabel(
            inner, text=badge,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=badge_color,
            width=34, height=18,
            corner_radius=3,
            fg_color=C_CARD
        )
        badge_lbl.pack(side="left", padx=(0, 10))

        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_col, text=display,
            font=ctk.CTkFont(size=12),
            text_color=C_TEXT, anchor="w"
        ).pack(fill="x")

        ctk.CTkLabel(
            text_col,
            text=f"{entry.get('date', '')}  ·  {badge}",
            font=ctk.CTkFont(size=10),
            text_color=C_FAINT, anchor="w"
        ).pack(fill="x")

        btn_open = ctk.CTkButton(
            inner, text="📂", width=30, height=30,
            corner_radius=5, fg_color="transparent",
            border_width=0,
            text_color=C_MUTED, hover_color=C_HOVER,
            font=ctk.CTkFont(size=15),
            command=lambda p=folder: self.open_folder(p)
        )
        btn_open.pack(side="right")

        if filepath and Path(filepath).exists():
            btn_play = ctk.CTkButton(
                inner, text="▶", width=30, height=30,
                corner_radius=5, fg_color="transparent",
                border_width=0,
                text_color=C_ACCENT, hover_color=C_HOVER,
                font=ctk.CTkFont(size=15),
                command=lambda p=filepath: self._play_from_history(p)
            )
            btn_play.pack(side="right", padx=(0, 4))

        # Linha separadora
        ctk.CTkFrame(item, height=1, fg_color=C_BORDER_SOFT, corner_radius=0).pack(fill="x")

        return item

    def _play_from_history(self, filepath):
        self._switch_panel("library")
        try:
            folder = Path(filepath).parent
            files = sorted(
                [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in MEDIA_EXTS],
                key=lambda f: f.name.lower()
            )
            self._library_populate(files)
            
            for i, (widget, fp) in enumerate(self._lib_file_items):
                if Path(fp).resolve() == Path(filepath).resolve():
                    self._lib_current_idx = i
                    for w, _ in self._lib_file_items:
                        w.configure(fg_color=C_BG)
                    widget.configure(fg_color=C_HOVER)
                    self._player_load_and_play(fp)
                    return
        except Exception:
            pass
            
        self._player_load_and_play(filepath)

    def add_active_download(self, title, kind):
        if getattr(self, "empty_label", None) is not None:
            try:
                self.empty_label.destroy()
            except Exception:
                pass
            self.empty_label = None

        item = ctk.CTkFrame(self.history_frame, corner_radius=0, fg_color=C_SURFACE, border_width=0)
        
        display = title if len(title) <= 65 else title[:62] + "..."
        badge = "MP3" if kind == "audio" else "MP4"
        badge_color = "#5B8DD9" if kind == "video" else C_ACCENT

        inner = ctk.CTkFrame(item, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=8)

        badge_lbl = ctk.CTkLabel(
            inner, text=badge, font=ctk.CTkFont(size=9, weight="bold"),
            text_color=badge_color, width=34, height=18,
            corner_radius=3, fg_color=C_CARD
        )
        badge_lbl.pack(side="left", padx=(0, 10))

        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_col, text=display, font=ctk.CTkFont(size=12),
            text_color=C_TEXT, anchor="w"
        ).pack(fill="x")

        self._active_dl_status = ctk.CTkLabel(
            text_col, text="Iniciando...", font=ctk.CTkFont(size=10),
            text_color=C_FAINT, anchor="w"
        )
        self._active_dl_status.pack(fill="x")
        
        self._active_dl_progress = ctk.CTkProgressBar(
            text_col, height=4, corner_radius=2,
            fg_color=C_BORDER, progress_color=C_ACCENT
        )
        self._active_dl_progress.pack(fill="x", pady=(4, 0))
        self._active_dl_progress.set(0)

        ctk.CTkFrame(item, height=1, fg_color=C_BORDER_SOFT, corner_radius=0).pack(fill="x")

        if self.history_widgets:
            item.pack(fill="x", padx=0, pady=0, before=self.history_widgets[0])
        else:
            item.pack(fill="x", padx=0, pady=0)
        
        self._active_dl_frame = item
        
        try:
            canvas = self.history_frame._parent_canvas
            canvas.yview_moveto(0)
        except Exception:
            pass

    def remove_active_download(self):
        if getattr(self, "_active_dl_frame", None):
            try:
                self._active_dl_frame.destroy()
            except Exception:
                pass
            self._active_dl_frame = None
            self._active_dl_progress = None
            self._active_dl_status = None

    def add_history_item(self, entry):
        self.history.insert(0, entry)
        save_history(self.history)

        if getattr(self, "empty_label", None) is not None:
            try:
                self.empty_label.destroy()
            except Exception:
                pass
            self.empty_label = None

        widget = self.build_history_widget(entry)
        if self.history_widgets:
            widget.pack(fill="x", padx=0, pady=0, before=self.history_widgets[0])
        else:
            widget.pack(fill="x", padx=0, pady=0)
        self.history_widgets.insert(0, widget)
        self.update_history_count()

        try:
            canvas = self.history_frame._parent_canvas
            canvas.yview_moveto(0)
        except Exception:
            pass

    def clear_history(self):
        if not self.history:
            messagebox.showinfo("Histórico", "O histórico já está vazio.", parent=self)
            return
        if not messagebox.askyesno(
            "Limpar histórico",
            f"Remover os {len(self.history)} registros do histórico?\n\n"
            "Os arquivos baixados NÃO serão apagados.",
            parent=self
        ):
            return
        self.history = []
        save_history(self.history)
        for widget in self.history_widgets:
            try:
                widget.destroy()
            except Exception:
                pass
        self.history_widgets = []
        if getattr(self, "empty_label", None) is None:
            self.empty_label = ctk.CTkLabel(
                self.history_frame, text="Nenhum download ainda.",
                font=ctk.CTkFont(size=12),
                text_color=C_FAINT
            )
            self.empty_label.pack(pady=24)
        self.update_history_count()
        self.set_status("Histórico limpo")

    # ==================== PROGRESSO ====================
    def _update_progress(self, percent, text):
        if percent is not None:
            try:
                val = max(0.0, min(1.0, float(percent)))
                self.progress.set(val)
                if getattr(self, "_active_dl_progress", None):
                    self._active_dl_progress.set(val)
            except (TypeError, ValueError):
                pass
        if text:
            self.set_status(text)
            if getattr(self, "_active_dl_status", None):
                self._active_dl_status.configure(text=text)

    def cancel_download(self):
        if not self.is_downloading:
            return
        self.cancel_event.set()
        self.cancel_btn.configure(state="disabled", text="Cancelando...")
        self.set_status("Cancelando, aguarde...")

    def _analysis_failed(self, message):
        self.finish_download(None)
        self.set_status("Erro ao ler o link")
        message = str(message)
        if len(message) > 600:
            message = message[:600] + "..."
        messagebox.showerror("Erro", f"Não foi possível ler o link:\n\n{message}", parent=self)

    def handle_analysis(self, info, original_url):
        entries = [e for e in list(info.get("entries") or []) if e]

        if entries and len(entries) > 1:
            # Playlists: deixa o usuário escolher os itens
            preselect = None
            try:
                if parse_qs(urlparse(original_url).query).get("v"):
                    preselect = {url_key(original_url)}
            except Exception:
                pass

            selector = PlaylistSelector(self, info.get("title") or "Playlist", entries, preselect)
            self.wait_window(selector)
            chosen = selector.result

            if not chosen:
                self.finish_download("Download cancelado")
                return

            items = []
            for entry in chosen:
                link = entry.get("webpage_url") or entry.get("url")
                if not link:
                    continue
                items.append({
                    "url": link,
                    "title": entry.get("title") or entry.get("id") or "Sem título",
                    "duration": entry.get("duration"),
                })
        else:
            link = info.get("webpage_url") or original_url
            title = info.get("title") or "Vídeo"
            items = [{"url": link, "title": title, "duration": info.get("duration")}]

        if not items:
            messagebox.showwarning("Aviso", "Nenhum item válido foi selecionado.", parent=self)
            self.finish_download("Download cancelado")
            return

        self.ensure_ffmpeg(items)

    # ==================== FFMPEG ====================
    def locate_ffmpeg(self, items):
        path = filedialog.askopenfilename(
            title="Selecione o arquivo ffmpeg.exe",
            parent=self,
            filetypes=[("FFmpeg", "ffmpeg.exe"), ("Programas", "*.exe"), ("Todos os arquivos", "*.*")]
        )
        if not path:
            self.finish_download("Download cancelado")
            return

        if not Path(path).name.lower().startswith("ffmpeg"):
            if not messagebox.askyesno(
                "Arquivo diferente",
                "O arquivo selecionado não se chama ffmpeg.exe.\n"
                "O app pode não conseguir converter para MP3.\n\nDeseja usá-lo mesmo assim?",
                parent=self
            ):
                self.finish_download("Download cancelado")
                return

        self.app_config["ffmpeg_path"] = str(path)
        save_config(self.app_config)
        self.ffmpeg_location = str(Path(path).parent)
        self.proceed_with(items)

    def _ffmpeg_target_dir(self):
        try:
            FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
            return FFMPEG_DIR
        except OSError:
            fallback = Path.home() / ".ld_youtube_downloader"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    def _ffmpeg_progress(self, percent, done, total):
        self.progress.set(max(0.0, min(1.0, percent)))
        self.set_status(
            f"Baixando FFmpeg... {done / (1024 * 1024):.1f} MB de {total / (1024 * 1024):.1f} MB ({percent * 100:.0f}%)"
        )

    def _ffmpeg_done(self):
        items = self._pending_items
        self._pending_items = None
        if items:
            self.proceed_with(items)
        else:
            self.finish_download(None)

    def _ffmpeg_failed(self, message):
        items = self._pending_items
        self._pending_items = None
        message = str(message)
        if len(message) > 400:
            message = message[:400] + "..."
        if items and messagebox.askyesno(
            "Falha ao baixar o FFmpeg",
            f"Não foi possível baixar automaticamente:\n\n{message}\n\n"
            "Deseja localizar o ffmpeg.exe manualmente?",
            parent=self
        ):
            self.locate_ffmpeg(items)
            return
        self.finish_download("FFmpeg não encontrado - download cancelado")
        messagebox.showerror(
            "FFmpeg necessário",
            "Sem o FFmpeg não é possível converter para MP3/MP4.\n\n"
            "Instale o FFmpeg e tente novamente: https://www.gyan.dev/ffmpeg/builds/",
            parent=self
        )

    # ==================== ARQUIVOS REPETIDOS ====================
    def check_duplicates(self, items):
        folder = Path(self._target_dir)
        try:
            existing = {f.name.lower() for f in folder.iterdir() if f.is_file()}
        except OSError:
            existing = set()
        stems = {Path(name).stem for name in existing}
        history_dates = {}
        for h in self.history:
            history_dates.setdefault(url_key(h.get("url")), h.get("date", ""))
        ext = "mp3" if self.download_type.get() == "audio" else "mp4"

        flagged = []
        for item in items:
            filename = sanitize_filename(item["title"]) + "." + ext
            reason = None
            if filename.lower() in existing:
                reason = f"já existe na pasta ({filename})"
            elif Path(filename).stem.lower() in stems:
                reason = "já existe em outro formato (ex.: .webm)"
            else:
                date = history_dates.get(url_key(item["url"]))
                if date:
                    reason = f"consta no histórico ({date})"
            if reason:
                item["reason"] = reason
                flagged.append(item)
        return flagged

    def build_duplicate_message(self, items, flagged):
        lines = []
        for item in flagged[:12]:
            title = item["title"]
            title = title if len(title) <= 55 else title[:52] + "..."
            lines.append(f"  • {title}\n      {item.get('reason', '')}")
        body = "\n".join(lines)
        if len(flagged) > 12:
            body += f"\n  ... e mais {len(flagged) - 12} item(ns)"

        if len(items) == 1:
            return (
                "Este arquivo já foi baixado antes:\n\n"
                f"{body}\n\n"
                "Deseja baixá-lo mesmo assim? O arquivo existente será substituído."
            )
        return (
            f"Atenção: {len(flagged)} de {len(items)} itens parecem já ter sido baixados:\n\n"
            f"{body}\n\n"
            "Deseja baixá-los mesmo assim? Os arquivos existentes serão substituídos.\n"
            "Se escolher NÃO, apenas os itens repetidos serão ignorados."
        )

    # ==================== EXECUÇÃO ====================
    def proceed_with(self, items):
        if self.cancel_event.is_set():
            self._pending_items = None
            self.finish_download("Download cancelado")
            return

        flagged = self.check_duplicates(items)
        overwrite = False

        if flagged:
            answer = messagebox.askyesno(
                "Arquivo já baixado",
                self.build_duplicate_message(items, flagged),
                parent=self
            )
            if len(items) == 1:
                if not answer:
                    self.finish_download("Download cancelado - arquivo já existe")
                    return
                overwrite = True
            elif answer:
                overwrite = True
            else:
                skip_ids = {id(item) for item in flagged}
                remaining = [item for item in items if id(item) not in skip_ids]
                if not remaining:
                    messagebox.showinfo(
                        "Tudo certo",
                        "Todos os itens selecionados já estão na pasta de destino.",
                        parent=self
                    )
                    self.finish_download("Nada a baixar - arquivos já existem")
                    return
                items = remaining

        self.start_download_thread(items, overwrite)

    def start_download_thread(self, items, overwrite):
        # captura as escolhas na thread principal: as threads worker do
        # yt-dlp não podem ler variáveis do Tk (RuntimeError)
        self._mode = self.download_type.get()
        self._quality = self.quality_menu.get()
        self._pending_items = items
        self.overwrite = overwrite
        self._download_started = True
        self.logger = YDLLogger()
        total = len(items)
        self.set_download_button(
            "Baixando..." if total == 1 else f"Baixando 1/{total}...",
            disabled=True
        )
        threading.Thread(target=self.download_thread, daemon=True).start()

    def _on_item_start(self, index, total, title):
        short = title if len(title) <= 50 else title[:47] + "..."
        self.progress.set(0)
        self.set_download_button(
            "Baixando..." if total == 1 else f"Baixando {index}/{total}...",
            disabled=True
        )
        self.set_status(f"[{index}/{total}] {short}")
        
        self.remove_active_download()
        self.add_active_download(title, self._mode)

    def _on_download_done(self, completed, failed, cancelled, total):
        self.remove_active_download()
        for entry in completed:
            self.add_history_item(entry)

        if cancelled:
            if completed:
                self.finish_download(f"Download cancelado ({len(completed)}/{total} concluídos)")
            else:
                self.finish_download("Download cancelado")
            return

        def problems():
            lines = []
            for f in failed[:10]:
                error = str(f.get("error") or "erro desconhecido")
                if len(error) > 200:
                    error = error[:200] + "..."
                lines.append(f"• {f.get('title', '?')}: {error}")
            if len(failed) > 10:
                lines.append(f"... e mais {len(failed) - 10} erro(s)")
            return "\n".join(lines)

        if failed and not completed:
            self.finish_download("Erro no download")
            messagebox.showerror("Erro", f"Nenhum arquivo foi baixado:\n\n{problems()}", parent=self)
        elif failed:
            self.finish_download(f"Concluído com {len(failed)} erro(s)")
            messagebox.showwarning(
                "Concluído com erros",
                f"{len(completed)} baixado(s) e {len(failed)} falha(s):\n\n{problems()}",
                parent=self
            )
        else:
            self.finish_download("Download finalizado!")
            if len(completed) == 1:
                messagebox.showinfo("Sucesso", "Download concluído com sucesso!", parent=self)
            else:
                messagebox.showinfo("Sucesso", f"{len(completed)} arquivo(s) baixado(s) com sucesso!", parent=self)

    def finish_download(self, status=None):
        self.remove_active_download()
        self.is_downloading = False
        self._pending_items = None
        self.set_download_button(BTN_DOWNLOAD, disabled=False)
        self.cancel_btn.configure(state="disabled", text=BTN_CANCEL)
        self.progress.set(0)
        self.progress.configure(progress_color=C_ACCENT)
        if status:
            self.set_status(status)

        # Se o download nem começou (link inválido, playlist cancelada,
        # duplicado recusado...), devolve o link para o campo.
        if not self._download_started and self._last_url:
            try:
                if not self.url_entry.get().strip():
                    self.url_entry.insert(0, self._last_url)
            except Exception:
                pass
        self._last_url = ""

    # ==================== OPÇÕES DO yt-dlp ====================
    def get_ydl_opts(self, logger):
        outtmpl = os.path.join(self._target_dir, "%(title)s.%(ext)s")

        opts = {
            "outtmpl": outtmpl,
            "progress_hooks": [self.progress_hook],
            "quiet": True,
            "no_warnings": True,
            "logger": logger,
            "ignoreerrors": True,
            "noplaylist": True,
            "retries": 3,
            "fragment_retries": 3,
            "noprogress": True,
            "overwrites": self.overwrite,
        }

        if self.ffmpeg_location:
            opts["ffmpeg_location"] = self.ffmpeg_location

        if self._mode == "audio":
            # Saída sempre em MP3
            kbps = re.search(r"(\d+)\s*kbps", self._quality, re.IGNORECASE)
            quality = kbps.group(1) if kbps else "192"
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality,
            }]
        else:
            # Saída sempre em MP4
            pixels = re.search(r"(\d{3,4})\s*p", self._quality, re.IGNORECASE)
            height = pixels.group(1) if pixels else None
            if height:
                opts["format"] = (
                    f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"bestvideo[height<={height}]+bestaudio/"
                    f"best[height<={height}][ext=mp4]/best[height<={height}]"
                )
            else:
                opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
            opts["merge_output_format"] = "mp4"
            opts["postprocessors"] = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]

        return opts

    def resolve_final_file(self, info, item):
        folder = Path(self._target_dir)
        prefer = "mp3" if self._mode == "audio" else "mp4"
        stem = sanitize_filename(info.get("title") or item["title"])

        candidates = []
        filepath = info.get("filepath")
        if filepath:
            candidates.append(filepath)
        candidates.append(str(folder / f"{stem}.{prefer}"))
        for ext in ("mp3", "mp4", "m4a", "webm", "mkv", "opus", "ogg", "aac"):
            candidates.append(str(folder / f"{stem}.{ext}"))

        for candidate in candidates:
            try:
                if os.path.isfile(candidate):
                    return candidate
            except OSError:
                continue

        try:
            lower_stem = stem.lower()
            for file in folder.iterdir():
                if file.is_file() and file.stem.lower() == lower_stem:
                    return str(file)
        except OSError:
            pass
        return None

    def cleanup_partial(self):
        """Remove arquivos .part / .ytdl deixados por um download cancelado."""
        current = self.current_file
        if not current:
            return
        folder = Path(current).parent
        base = Path(current).name
        try:
            for file in folder.iterdir():
                if not file.is_file():
                    continue
                name = file.name
                if name == base:
                    continue
                if name.startswith(base + ".part") or name.startswith(base + ".ytdl"):
                    try:
                        file.unlink()
                    except OSError:
                        pass
        except OSError:
            pass


if __name__ == "__main__":
    app = LDYouTubeDownloader()
    app.mainloop()
