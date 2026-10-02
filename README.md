# LD Youtube Downloader

<div align="center">

![LD Youtube Downloader](Prints/tela%20inicial%20-%20LD%20Youtube%20Downloader.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)](https://github.com/LDElectric/LD-Youtube-Downloader/releases)

**Baixe vídeos e músicas do YouTube com qualidade e facilidade.**

[⬇ Download do Executável](https://github.com/LDElectric/LD-Youtube-Downloader/releases/latest) · [📄 Licença MIT](LICENSE)

</div>

---

## 📋 Sobre o Projeto

O **LD Youtube Downloader** é um aplicativo desktop para Windows que permite baixar e assistir vídeo aulas, documentários e qualquer conteúdo do YouTube diretamente no seu computador — sem precisar de conexão com a internet depois de salvar.

Ideal para quem quer:
- 📚 **Baixar e assistir vídeo aulas offline** — quando e onde quiser, sem depender de internet
- 🎵 **Salvar as músicas prediletas** — fazendo download do áudio de qualquer vídeo em MP3
- 🎬 **Assistir vídeos offline** — economizando dados ou usando em locais sem internet

---

## ✨ Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| ⬇ **Download de Vídeo** | Baixe vídeos em MP4 com qualidades de 360p até 1080p |
| 🎵 **Download de Áudio** | Extraia o áudio como MP3 em até 320 kbps |
| 📂 **Conversor de Mídia** | Converta arquivos locais entre MP3, MP4, WAV, AAC, FLAC, OGG e mais |
| 📚 **Biblioteca** | Veja e gerencie todo o seu histórico de downloads |
| ▶ **Player Integrado** | Reproduza áudios diretamente no aplicativo |
| 🔗 **Suporte a Playlists** | Baixe múltiplos vídeos de uma playlist de uma vez |
| 🌙 **Interface Escura** | Design moderno e profissional com tema escuro |

---

## 🖥 Requisitos para o Executável

| Requisito | Detalhe |
|---|---|
| Sistema Operacional | Windows 10 / 11 (64-bit) |
| FFmpeg | **Necessário** para conversão e download de MP3. O app detecta automaticamente se já estiver instalado ou pode ser configurado manualmente |

> **Dica:** Se o FFmpeg não for encontrado automaticamente, o aplicativo oferece a opção de baixá-lo automaticamente na primeira execução.

---

## 🚀 Como Usar

### Usando o Executável (Recomendado)

1. Acesse a página de [**Releases**](https://github.com/LDElectric/LD-Youtube-Downloader/releases/latest)
2. Baixe o arquivo `LD Youtube Downloader.exe`
3. Execute o arquivo — **não precisa instalar nada**

### Rodando pelo Código-Fonte

**Pré-requisitos:**
- Python 3.10+
- FFmpeg instalado e no PATH (ou configurado no app)

**Instalação:**
```bash
# Clone o repositório
git clone https://github.com/LDElectric/LD-Youtube-Downloader.git
cd LD-Youtube-Downloader

# Instale as dependências
pip install customtkinter yt-dlp pygame
```

**Execução:**
```bash
python LD_Youtube_Downloader.py
```

---

## 📁 Estrutura do Projeto

```
LD-Youtube-Downloader/
 ├── LD_Youtube_Downloader.py     # Ponto de entrada e janela principal
 ├── LD_Youtube_Downloader.ico    # Ícone do aplicativo
 │
 ├── core/
 │    ├── config.py               # Configurações, constantes e utilitários
 │    └── logger.py               # Logger do yt-dlp
 │
 └── ui/
      └── mixins/
           ├── player_mixin.py    # Lógica do player de áudio (pygame)
           ├── converter_mixin.py # Lógica de conversão de mídia (FFmpeg)
           └── downloader_mixin.py # Lógica de download (yt-dlp)
```

---

## 🛠 Tecnologias

- **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)** — Interface gráfica moderna
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — Motor de download
- **[FFmpeg](https://ffmpeg.org/)** — Conversão e processamento de mídia
- **[Pygame](https://www.pygame.org/)** — Player de áudio integrado

---

## 📜 Licença

Distribuído sob a licença **MIT**. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.

---

<div align="center">
Feito com ❤️ por <a href="https://github.com/LDElectric">Leonam Dias</a>
</div>
