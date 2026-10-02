import os
import re
import json
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ==================== CONFIGURAÇÃO ====================
CONFIG_FILE = Path.home() / ".youtube_downloader_config.json"
HISTORY_FILE = Path.home() / ".youtube_downloader_history.json"

# FFmpeg: necessário para converter o áudio para MP3 e mesclar/convertar vídeos para MP4
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_EXE = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
FFMPEG_DIR = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / "LD Youtube Downloader" / "ffmpeg"

# Limite de itens desenhados na tela (o histórico completo fica salvo no arquivo)
MAX_HISTORY_RENDER = 300
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# ==================== PALETA / DESIGN ====================
# Cinza médio profissional + detalhes em azul
C_BG          = "#3A3D44"   # fundo principal (cinza médio claro)
C_TOPBAR      = "#2E3138"   # barra superior/sidebar (mais escura)
C_SIDEBAR     = "#2E3138"   # sidebar
C_PANEL       = "#3A3D44"   # painel de conteúdo
C_CARD        = "#44474F"   # cartões/itens
C_SURFACE     = "#33363D"   # fundo de listas
C_BORDER      = "#52555F"   # bordas visíveis
C_BORDER_SOFT = "#42454D"   # bordas discretas
C_INPUT_BG    = "#2A2D34"   # fundo de inputs
C_TEXT        = "#E2E5EA"   # texto principal
C_MUTED       = "#9BA4B0"   # texto secundário
C_FAINT       = "#62676F"   # texto fraco / placeholder
C_TRACK       = "#52555F"   # trilho de barra de progresso
C_HOVER       = "#484B54"   # hover de botões
C_ACCENT      = "#4A8FE8"   # azul principal
C_ACCENT_HOVER = "#3A7DD4"
C_ACCENT_SOFT  = "#1C2E50"
C_ACCENT_DIM   = "#295090"  # acento desativado
C_DANGER       = "#E86060"
C_DANGER_HOVER = "#3A1818"
C_SUCCESS      = "#5CB870"
C_WHITE        = "#FFFFFF"
C_ICON         = "#7A8090"  # ícones inativos
C_ICON_ACTIVE  = "#4A8FE8"  # ícone ativo
C_SEG_BG       = "#2A2D34"  # fundo do segmented button
C_SEG_SEL      = "#44474F"  # item selecionado

BTN_DOWNLOAD = "  ⬇  Baixar"
BTN_CANCEL = "Cancelar"

# Formatos para o conversor
CONV_FORMATS = ["MP3", "MP4", "WAV", "AAC", "M4A", "OGG", "FLAC", "WEBM", "AVI", "MKV", "OPUS"]
MEDIA_EXTS   = {".mp3", ".mp4", ".wav", ".aac", ".m4a", ".ogg", ".flac", ".webm",
                ".avi", ".mkv", ".opus", ".mov", ".wma", ".flv"}
VIDEO_EXTS   = {".mp4", ".avi", ".mkv", ".webm", ".mov", ".flv"}

VIDEO_QUALITIES = ["720p", "1080p", "480p", "360p", "Melhor qualidade"]
AUDIO_QUALITIES = ["192 kbps", "320 kbps", "256 kbps", "128 kbps"]


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"last_dir": str(Path.home() / "Downloads")}


def save_config(data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def load_history():
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def save_history(items):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def url_key(url):
    """Normaliza o link para detectar repetições (mesmo vídeo, links diferentes)."""
    if not url:
        return ""
    try:
        query = parse_qs(urlparse(url).query)
        if query.get("v"):
            return "yt:" + query["v"][0]
    except Exception:
        pass
    return str(url)


def fmt_duration(seconds):
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_ffmpeg(app_config):
    """Procura o ffmpeg em: configuração salva, PATH, pasta do app e cache do app."""
    candidates = []
    saved = app_config.get("ffmpeg_path")
    if saved:
        candidates.append(Path(saved))
    for name in ("ffmpeg", "ffmpeg.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    base = app_dir()
    for path in (
        FFMPEG_DIR / FFMPEG_EXE,
        base / FFMPEG_EXE,
        base / "bin" / FFMPEG_EXE,
        base / "ffmpeg" / FFMPEG_EXE,
    ):
        candidates.append(path)
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate.parent)
        except OSError:
            continue
    return None
