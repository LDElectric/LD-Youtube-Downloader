import os, time, threading, re, shutil, urllib.request, zipfile, json, ctypes, sys
from pathlib import Path
import yt_dlp
from yt_dlp.utils import DownloadCancelled
from core.config import *
from core.logger import YDLLogger

class DownloaderMixin:
    def progress_hook(self, d):
        filename = d.get("filename")
        if filename:
            self.current_file = filename

        status = d.get("status")

        # Cancelamento: interrompe o download atual
        if status == "downloading" and self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelado pelo usuário")

        if status == "downloading":
            now = time.monotonic()
            if now - self._last_hook_ui < 0.2:
                return
            self._last_hook_ui = now
            try:
                percent = float(str(d.get("_percent_str", "0")).replace("%", "").strip() or 0) / 100
            except ValueError:
                percent = None
            speed = d.get("_speed_str", "N/A")
            eta = d.get("_eta_str", "N/A")
            text = f"Baixando... {d.get('_percent_str', '')} | Velocidade: {speed} | ETA: {eta}"
            self.ui(self._update_progress, percent, text)
        elif status == "finished":
            self.ui(self._update_progress, 1, "Processando arquivo...")

    # ==================== FLUXO DE DOWNLOAD ====================
    def start_download(self):
        if self.is_downloading:
            return

        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Aviso", "Cole um link válido do YouTube.", parent=self)
            return

        # Limpa o campo para já poder colar o próximo link
        self.url_entry.delete(0, "end")

        self._target_dir = self.download_path
        self._last_url = url
        self._download_started = False
        self.is_downloading = True
        self.cancel_event.clear()
        self._pending_items = None
        self.current_file = None

        self.set_download_button("Analisando link...", disabled=True)
        self.cancel_btn.configure(state="normal", text=BTN_CANCEL)
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

        if self.cancel_event.is_set():
            self.ui(self.finish_download, "Download cancelado")
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
                        if self.cancel_event.is_set():
                            raise DownloadCancelled("Download cancelado pelo usuário")
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
        except DownloadCancelled:
            if zip_path:
                try:
                    zip_path.unlink()
                except OSError:
                    pass
            self._pending_items = None
            self.ui(self.finish_download, "Download cancelado")
        except Exception as e:
            if zip_path:
                try:
                    zip_path.unlink()
                except OSError:
                    pass
            self.ui(self._ffmpeg_failed, str(e))

    def download_thread(self):
        items = self._pending_items or []
        self._pending_items = None
        total = len(items)
        completed, failed = [], []
        logger = self.logger

        try:
            opts = self.get_ydl_opts(logger)
            with yt_dlp.YoutubeDL(opts) as ydl:
                for index, item in enumerate(items, 1):
                    if self.cancel_event.is_set():
                        break

                    self.current_file = None
                    logger.reset()
                    self.ui(self._on_item_start, index, total, item["title"])

                    try:
                        info = ydl.extract_info(item["url"], download=True)
                    except DownloadCancelled:
                        break
                    except Exception as e:
                        if self.cancel_event.is_set():
                            break
                        failed.append({
                            "title": item["title"],
                            "error": logger.last_error() or str(e) or "erro desconhecido",
                        })
                        continue

                    if self.cancel_event.is_set():
                        break

                    if info is None:
                        failed.append({
                            "title": item["title"],
                            "error": logger.last_error() or "link indisponível",
                        })
                        continue

                    final_file = self.resolve_final_file(info, item)
                    if final_file is None:
                        failed.append({
                            "title": item["title"],
                            "error": "arquivo não encontrado na pasta de destino",
                        })
                        continue

                    completed.append({
                        "title": info.get("title") or item["title"],
                        "folder": str(Path(final_file).parent),
                        "filepath": final_file,
                        "url": item["url"],
                        "kind": self._mode,
                        "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    })
        except Exception as e:
            if not self.cancel_event.is_set():
                failed.append({"title": "Download", "error": str(e)})
        finally:
            if self.cancel_event.is_set():
                self.cleanup_partial()

        cancelled = self.cancel_event.is_set()
        self.ui(self._on_download_done, completed, failed, cancelled, total)

