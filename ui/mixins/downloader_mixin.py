import os, time, threading, re, shutil, urllib.request, zipfile, json, ctypes, sys
from datetime import datetime
from pathlib import Path
import yt_dlp
from yt_dlp.utils import DownloadCancelled
from core.config import *
from core.logger import YDLLogger

class DownloaderMixin:
    # ==================== FLUXO DE DOWNLOAD ====================
    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Aviso", "Cole um link válido do YouTube.", parent=self)
            return

        # Limpa o campo para já poder colar o próximo link
        self.url_entry.delete(0, "end")

        self._target_dir = self.download_path
        self._last_url = url
        self._download_started = False

        self.set_download_button("Analisando link...", disabled=True)
        self.progress.set(0)
        self.progress.configure(progress_color=C_ACCENT)
        self.set_status("Obtendo informações do link...")

        threading.Thread(target=self.analyze_thread, args=(url,), daemon=True).start()

    def analyze_thread(self, url):
        try:
            opts = {
                "extract_flat": "in_playlist",
                "skip_download": True,
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            self.ui(self._analysis_failed, str(e))
            return

        if not info:
            self.ui(self._analysis_failed, "Não foi possível obter informações do link.")
            return

        self.ui(self.handle_analysis, info, url)

    def ensure_ffmpeg(self, items):
        """Garante o FFmpeg (obrigatório para gerar MP3/MP4)."""
        if self.ffmpeg_location:
            self.proceed_with(items)
            return

        choice = messagebox.askyesnocancel(
            "FFmpeg necessário",
            "O FFmpeg não foi encontrado neste computador.\n\n"
            "Ele é obrigatório para converter os arquivos para MP3/MP4 "
            "(sem ele o app geraria arquivos .webm).\n\n"
            "Deseja baixá-lo automaticamente?\n\n"
            "• SIM: baixa e instala automaticamente (≈110 MB, só uma vez)\n"
            "• NÃO: você localiza o arquivo ffmpeg.exe manualmente\n"
            "• CANCELAR: aborta o download",
            parent=self
        )

        if choice is None:
            self.finish_download("Download cancelado")
            return

        if choice:
            self._pending_items = items
            self.set_download_button("Baixar FFmpeg...", disabled=True)
            threading.Thread(target=self.ffmpeg_download_thread, daemon=True).start()
        else:
            self.locate_ffmpeg(items)

    def ffmpeg_download_thread(self):
        zip_path = None
        try:
            target_dir = self._ffmpeg_target_dir()
            zip_path = target_dir / "ffmpeg-release.zip"
            self.ui(self.set_status, "Baixando FFmpeg (primeira vez apenas)...")

            request = urllib.request.Request(
                FFMPEG_URL,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=30) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                with open(zip_path, "wb") as fh:
                    while True:
                        chunk = resp.read(256 * 1024)
                        if not chunk:
                            break
                        fh.write(chunk)
                        done += len(chunk)
                        if total:
                            self.ui(self._ffmpeg_progress, done / total, done, total)

            self.ui(self.set_status, "Instalando FFmpeg...")
            with zipfile.ZipFile(zip_path) as zf:
                member = None
                for name in zf.namelist():
                    if name.replace("\\", "/").lower().endswith("/bin/" + FFMPEG_EXE.lower()):
                        member = name
                        break
                if member is None:
                    raise RuntimeError("Estrutura inesperada no pacote do FFmpeg.")
                dest = target_dir / FFMPEG_EXE
                with zf.open(member) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)

            try:
                zip_path.unlink()
            except OSError:
                pass

            self.app_config["ffmpeg_path"] = str(target_dir / FFMPEG_EXE)
            save_config(self.app_config)
            self.ffmpeg_location = str(target_dir)
            self.ui(self._ffmpeg_done)
        except Exception as e:
            if zip_path:
                try:
                    zip_path.unlink()
                except OSError:
                    pass
            self.ui(self._ffmpeg_failed, str(e))
