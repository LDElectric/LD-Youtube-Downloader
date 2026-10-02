import os, subprocess, threading
from tkinter import filedialog
from pathlib import Path
import customtkinter as ctk
from core.config import *

class ConverterMixin:
    def _conv_select_files(self):
        media_types = [
            ("Arquivos de mídia",
             "*.mp3 *.mp4 *.wav *.aac *.m4a *.ogg *.flac *.webm *.avi *.mkv *.opus *.mov *.wma"),
            ("Todos os arquivos", "*.*")]
        files = filedialog.askopenfilenames(title="Selecionar arquivos",
                                             filetypes=media_types, parent=self)
        if files:
            self._conv_set_files(list(files))

    def _conv_select_folder(self):
        path = filedialog.askdirectory(parent=self)
        if not path:
            return
        files = sorted([str(f) for f in Path(path).iterdir()
                        if f.is_file() and f.suffix.lower() in MEDIA_EXTS])
        if not files:
            messagebox.showinfo("Pasta vazia", "Nenhum arquivo de mídia encontrado na pasta.", parent=self)
            return
        self._conv_set_files(files)

    def _conv_set_files(self, files):
        self._converter_files = files
        for widget, _, __ in self._conv_file_widgets:
            try:
                widget.destroy()
            except Exception:
                pass
        self._conv_file_widgets = []
        try:
            if self._conv_empty_lbl:
                self._conv_empty_lbl.pack_forget()
        except Exception:
            pass
        for fp in files:
            self._conv_add_file_row(fp)
        n = len(files)
        self._conv_count_lbl.configure(text=f"{n} arquivo{'s' if n != 1 else ''}")
        self._conv_status_lbl.configure(text="Pronto para converter")
        self._conv_progress.set(0)
        self.update_idletasks()

    def _conv_start(self):
        if not self._converter_files:
            messagebox.showwarning("Aviso", "Selecione arquivos para converter.", parent=self)
            return
        if not self.ffmpeg_location:
            messagebox.showerror("FFmpeg necessário",
                                  "FFmpeg não encontrado.\nUse a aba Downloads para baixá-lo primeiro.",
                                  parent=self)
            return
        out_fmt = self._conv_format.get().lower()
        delete_orig = self._conv_delete_orig.get()
        files_to_conv = [fp for fp in self._converter_files
                         if Path(fp).suffix.lower().lstrip(".") != out_fmt]
        if not files_to_conv:
            messagebox.showinfo("Nada a converter",
                                 "Todos os arquivos já estão no formato selecionado.", parent=self)
            return
        self._conv_start_btn.configure(state="disabled", text="Convertendo...")
        self._conv_status_lbl.configure(text="Iniciando conversão...")
        self._conv_progress.set(0)
        for _, __, lbl in self._conv_file_widgets:
            lbl.configure(text="", text_color=C_FAINT)
        threading.Thread(target=self._conv_thread,
                         args=(files_to_conv, out_fmt, delete_orig), daemon=True).start()

    def _conv_thread(self, files, out_fmt, delete_orig):
        total = len(files)
        widget_map = {fp: lbl for _, fp, lbl in self._conv_file_widgets}
        ffmpeg_exe = str(Path(self.ffmpeg_location) /
                         ("ffmpeg.exe" if os.name == "nt" else "ffmpeg"))

        for i, filepath in enumerate(files):
            self.ui(self._conv_status_lbl.configure,
                    text=f"[{i+1}/{total}] {Path(filepath).name[:55]}...")
            self.ui(self._conv_progress.set, i / total)
            if filepath in widget_map:
                self.ui(widget_map[filepath].configure, text="⏳ aguardando", text_color=C_MUTED)

            out_path = str(Path(filepath).parent / (Path(filepath).stem + "." + out_fmt))
            cmd = [ffmpeg_exe, "-i", filepath, "-y"]

            # Opções por formato de saída
            if out_fmt == "mp3":
                cmd += ["-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k"]
            elif out_fmt in ("aac", "m4a"):
                cmd += ["-vn", "-c:a", "aac", "-b:a", "192k"]
            elif out_fmt == "wav":
                cmd += ["-vn", "-ar", "44100", "-ac", "2"]
            elif out_fmt == "ogg":
                cmd += ["-vn", "-c:a", "libvorbis", "-q:a", "4"]
            elif out_fmt == "flac":
                cmd += ["-vn", "-c:a", "flac"]
            elif out_fmt == "opus":
                cmd += ["-vn", "-c:a", "libopus", "-b:a", "128k"]
            elif out_fmt in ("mp4", "mkv", "avi", "webm"):
                cmd += ["-c:v", "copy", "-c:a", "aac"]
            cmd.append(out_path)

            try:
                kwargs = {}
                if os.name == 'nt':
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, encoding='utf-8', errors='replace', **kwargs)
                if result.returncode == 0 and Path(out_path).exists():
                    if delete_orig and Path(filepath).exists():
                        try:
                            Path(filepath).unlink()
                        except OSError:
                            pass
                    if filepath in widget_map:
                        self.ui(widget_map[filepath].configure,
                                text="✓ OK", text_color=C_SUCCESS)
                else:
                    if filepath in widget_map:
                        self.ui(widget_map[filepath].configure,
                                text="✗ Erro", text_color=C_DANGER)
            except subprocess.TimeoutExpired:
                if filepath in widget_map:
                    self.ui(widget_map[filepath].configure, text="✗ Timeout", text_color=C_DANGER)
            except Exception:
                if filepath in widget_map:
                    self.ui(widget_map[filepath].configure, text="✗ Falha", text_color=C_DANGER)

        self.ui(self._conv_progress.set, 1.0)
        self.ui(self._conv_status_lbl.configure, text=f"Conversão concluída! ({total} arquivo(s))")
        self.ui(self._conv_start_btn.configure, state="normal", text="⚡ Converter")

    # ==================== UTILIDADES DE UI ====================
