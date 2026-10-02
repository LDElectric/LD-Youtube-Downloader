class YDLLogger:
    """Coleta as mensagens do yt-dlp para mostrar o motivo real de uma falha."""

    def __init__(self):
        self.lines = []
        self.errors = []

    def reset(self):
        self.lines.clear()
        self.errors.clear()

    def debug(self, msg):
        self.lines.append(msg)

    def info(self, msg):
        self.lines.append(msg)

    def warning(self, msg):
        self.lines.append(msg)

    def error(self, msg):
        self.errors.append(msg)

    def last_error(self):
        for raw in reversed(self.errors):
            text = ANSI_RE.sub("", str(raw)).strip()
            if text.upper().startswith("ERROR:"):
                text = text[6:].strip()
            if text:
                return text
        return None


