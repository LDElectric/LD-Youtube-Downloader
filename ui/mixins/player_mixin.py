import os, subprocess, time
from pathlib import Path
from core.config import *
try:
    import pygame
except ImportError:
    pass

class PlayerMixin:
    def _player_toggle(self):
        if not PYGAME_AVAILABLE:
            messagebox.showerror("pygame não instalado",
                                  "Instale o pygame para usar o player:\npip install pygame", parent=self)
            return
        if self._player_state == "playing":
            self._player_pause()
        elif self._player_state == "paused":
            self._player_resume()
        elif self._player_file:
            self._player_play_file(self._player_file)

    def _player_play_file(self, filepath):
        if not PYGAME_AVAILABLE:
            return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            pygame.mixer.music.set_volume(self._player_vol.get())
            self._player_state = "playing"
            self._player_play_btn.configure(text="⏸")
            self._player_update_loop()
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível reproduzir:\n{e}", parent=self)

    def _player_pause(self):
        if PYGAME_AVAILABLE:
            pygame.mixer.music.pause()
        self._player_state = "paused"
        self._player_play_btn.configure(text="▶")

    def _player_resume(self):
        if PYGAME_AVAILABLE:
            pygame.mixer.music.unpause()
        self._player_state = "playing"
        self._player_play_btn.configure(text="⏸")
        self._player_update_loop()

    def _player_stop(self):
        if PYGAME_AVAILABLE:
            pygame.mixer.music.stop()
        self._player_state = "stopped"
        self._player_play_btn.configure(text="▶")
        self._player_progress.set(0)
        self._player_time_lbl.configure(text="0:00")

    def _player_prev(self):
        if self._lib_current_idx > 0 and self._lib_file_items:
            self._lib_current_idx -= 1
            _, fp = self._lib_file_items[self._lib_current_idx]
            self._player_load_and_play(fp)

    def _player_next(self):
        if self._lib_file_items and self._lib_current_idx < len(self._lib_file_items) - 1:
            self._lib_current_idx += 1
            _, fp = self._lib_file_items[self._lib_current_idx]
            self._player_load_and_play(fp)

    def _player_seek(self, value):
        if not PYGAME_AVAILABLE or self._player_duration <= 0:
            return
        pos_sec = float(value) * self._player_duration / 100.0
        try:
            pygame.mixer.music.set_pos(pos_sec)
        except Exception:
            pass

    def _player_set_volume(self, value):
        if PYGAME_AVAILABLE:
            pygame.mixer.music.set_volume(float(value))

    def _player_update_loop(self):
        if self._player_state != "playing" or not PYGAME_AVAILABLE:
            return
        try:
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms >= 0 and self._player_duration > 0:
                pos_sec = pos_ms / 1000.0
                pct = min(100.0, (pos_sec / self._player_duration) * 100.0)
                self._player_progress.set(pct)
                self._player_time_lbl.configure(text=fmt_duration(int(pos_sec)))
            if not pygame.mixer.music.get_busy():
                # Acabou — tenta próxima faixa
                self._player_state = "stopped"
                self._player_play_btn.configure(text="▶")
                self._player_next()
                return
        except Exception:
            pass
        self.after(400, self._player_update_loop)

    def _player_load_and_play(self, filepath):
        self._player_load_file(filepath)
        ext = Path(filepath).suffix.lower()
        if ext not in VIDEO_EXTS and PYGAME_AVAILABLE:
            self._player_play_file(filepath)

    def _player_load_file(self, filepath):
        self._player_file = filepath
        self._player_stop()
        ext = Path(filepath).suffix.lower()
        is_video = ext in VIDEO_EXTS
        self._player_type_lbl.configure(text="🎬" if is_video else "🎵")
        stem = Path(filepath).stem
        self._player_title_lbl.configure(text=stem[:55] + "..." if len(stem) > 55 else stem)
        dur = self._get_media_duration(filepath)
        self._player_duration = dur
        dur_str = fmt_duration(int(dur)) if dur > 0 else "?"
        self._player_total_lbl.configure(text=dur_str)
        self._player_info_lbl.configure(text=f"{ext.upper().lstrip('.')}  ·  {dur_str}")

    def _get_media_duration(self, filepath):
        """Retorna duração em segundos via ffprobe."""
        if not self.ffmpeg_location:
            return 0.0
        try:
            probe_name = "ffprobe.exe" if os.name == "nt" else "ffprobe"
            probe_path = Path(self.ffmpeg_location) / probe_name
            if not probe_path.exists():
                probe_path = Path(shutil.which("ffprobe") or "ffprobe")
            kwargs = {}
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                [str(probe_path), "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", filepath],
                capture_output=True, text=True, timeout=8, encoding='utf-8', errors='replace', **kwargs)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _player_open_system(self):
        if self._player_file:
            self.open_folder(str(Path(self._player_file).parent))

    # ==================== BIBLIOTECA METHODS ====================
