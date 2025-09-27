# 🎵 YTVLC – YouTube to VLC Player
<img width="512" height="512" alt="YTVLC_icon" src="https://github.com/user-attachments/assets/b066e181-b989-43ad-9384-1d6a1bea4f59" />

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![AD Free](https://img.shields.io/badge/AD-Free-blue.svg)
![Lightweight](https://img.shields.io/badge/Low_CPU_&_RAM-lightgrey.svg)
![Made with Python](https://img.shields.io/badge/Made_with-Python-yellow.svg)

Aplicação leve em **Python + Tkinter** que permite:
- Pesquisar músicas ou playlists no YouTube (NO ADS)
- Reproduzir diretamente no **VLC** (áudio ou vídeo)
- Fazer download em **MP3 (áudio)** ou **MP4 (vídeo)**
- Interface simples e escura

---

## 🚀 Como usar

### 🔹 Opção 1 – Usar o `.exe` (mais fácil)
1. Instala o [VLC Media Player](https://www.videolan.org/vlc/).
2. Faz download da Release (ficheiro `.zip` ou `.exe`).
3. Garante que a estrutura está assim:
   ```
   YTVLC_App/
     YTVLC.exe
     ffmpeg/
       bin/
         ffmpeg.exe
         ffprobe.exe
   ```
   > ⚠️ O **FFmpeg** já vai incluído no pacote. Não precisas instalar nada.
4. Corre o `YTVLC.exe` → pronto!

---

### 🔹 Opção 2 – Correr o código fonte
1. Instala o [Python 3.11+](https://www.python.org/downloads/).
2. Instala as dependências:
   ```bash
   pip install yt-dlp pillow requests
   ```
3. Garante que tens o [VLC](https://www.videolan.org/vlc/) instalado.
4. (Opcional, para downloads MP3/MP4) instala o [FFmpeg](https://ffmpeg.org/download.html) e mete no PATH.
5. Corre:
   ```bash
   python ytvlc_gui.py
   ```

---

## 📦 Tecnologias usadas
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) → extração de links e downloads
- [tkinter](https://docs.python.org/3/library/tkinter.html) → interface gráfica
- [VLC](https://www.videolan.org/) → player de áudio/vídeo
- [FFmpeg](https://ffmpeg.org/) → conversão para MP3/MP4
- [Pillow](https://python-pillow.org/) + [Requests](https://docs.python-requests.org/) → thumbnails

---

## 💡 Vantagens
- **Sem anúncios** (*AD Free*)
- **Consumo baixo de CPU e memória** comparado a abrir o YouTube no navegador
- **Leve e rápido**, pensado para uso diário sem pesar no sistema (Gaming)

---

## 📝 Notas
- Não são necessários **MPV**, navegadores, ou dependências extra.
- A pesquisa de playlists pode demorar alguns segundos.
- Para reduzir consumo de dados → usa os botões **Áudio** (não abre vídeo).
- Testado em **Windows 10/11**.

---

## 📜 Licença
MIT – usa à vontade, mas sem garantias 😉
