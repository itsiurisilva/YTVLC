import io, os, sys, json, shutil, subprocess, threading, requests, urllib.parse, platform
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageTk
import yt_dlp
import tkinter as tk
from tkinter import ttk, messagebox

# ---------- helpers de paths (script vs .exe) ----------
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = app_dir()
DOWNLOAD_DIR = os.path.join(BASE_DIR, "Downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

# ---------- defaults ----------
DEFAULTS = {
    "playlist_limit": 25,
    "network_caching_ms": 750,  # VLC network cache
    "vlc_path": "",             # se vazio: auto
    "ffmpeg_dir": "",           # se vazio: auto (usa .\ffmpeg\bin ou PATH)
}

# ---------- carregar settings ----------
def load_settings():
    cfg = DEFAULTS.copy()
    try:
        if os.path.isfile(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
                cfg.update({k: v for k, v in user.items() if k in cfg})
    except Exception:
        pass
    return cfg

CFG = load_settings()

# ---------- deteção de VLC ----------
def common_vlc_candidates():
    sysname = platform.system().lower()
    cand = []
    if sysname == "windows":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pfx = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        cand += [
            os.path.join(pf, "VideoLAN", "VLC", "vlc.exe"),
            os.path.join(pfx, "VideoLAN", "VLC", "vlc.exe"),
        ]
    elif sysname == "darwin":  # macOS
        cand += ["/Applications/VLC.app/Contents/MacOS/VLC"]
    else:  # linux/unix
        cand += [shutil.which("vlc") or "/usr/bin/vlc"]
    return [c for c in cand if c]

def locate_vlc():
    # 1) settings.json
    if CFG.get("vlc_path"):
        p = CFG["vlc_path"]
        if os.path.isfile(p):
            return p
    # 2) PATH
    w = shutil.which("vlc")
    if w:
        return w
    # 3) candidatos conhecidos
    for c in common_vlc_candidates():
        if c and os.path.isfile(c):
            return c
    return None

VLC_EXE = locate_vlc()

# ---------- deteção de FFmpeg ----------
def locate_ffmpeg_dir():
    # 1) settings.json
    if CFG.get("ffmpeg_dir"):
        d = CFG["ffmpeg_dir"]
        if os.path.isfile(os.path.join(d, "ffmpeg.exe")) or os.path.isfile(os.path.join(d, "ffmpeg")):
            if os.path.isfile(os.path.join(d, "ffprobe.exe")) or os.path.isfile(os.path.join(d, "ffprobe")):
                return d
    # 2) ./ffmpeg/bin ao lado do app
    local_bin = os.path.join(BASE_DIR, "ffmpeg", "bin")
    if os.path.isfile(os.path.join(local_bin, "ffmpeg.exe")) or os.path.isfile(os.path.join(local_bin, "ffmpeg")):
        if os.path.isfile(os.path.join(local_bin, "ffprobe.exe")) or os.path.isfile(os.path.join(local_bin, "ffprobe")):
            return local_bin
    # 3) PATH
    which_ffmpeg = shutil.which("ffmpeg") or ""
    which_ffprobe = shutil.which("ffprobe") or ""
    d1 = os.path.dirname(which_ffmpeg) if which_ffmpeg else ""
    d2 = os.path.dirname(which_ffprobe) if which_ffprobe else ""
    if d1 and d2 and d1 == d2:
        return d1
    return ""

FFMPEG_DIR = locate_ffmpeg_dir()

def have_ffmpeg() -> bool:
    return bool(FFMPEG_DIR)

# ---------- parametros gerais ----------
MAX_RESULTS = 8
THUMB_W, THUMB_H = 160, 90
THUMB_THREADS = 6
SOCKET_TIMEOUT = 5
YTDLP_RETRIES = 1
PLAYLIST_LIMIT = int(CFG.get("playlist_limit", 25))
NETWORK_CACHING = int(CFG.get("network_caching_ms", 750))

# HTTP session com User-Agent (YouTube gosta disto)
HTTP = requests.Session()
HTTP.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/127.0.0.1 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.youtube.com/",
})

# ---------- VLC ----------
def open_in_vlc(url, title=None, audio_only=True):
    exe = VLC_EXE or "vlc"
    if not VLC_EXE and not shutil.which(exe):
        messagebox.showerror("VLC não encontrado",
                             "Instala o VLC ou define 'vlc_path' no settings.json.")
        return
    safe_title = (title or "").replace("{", "(").replace("}", ")")
    args = [exe,
            "--one-instance",
            "--playlist-enqueue",
            "--playlist-autostart",
            "--no-video-title-show",
            f"--network-caching={NETWORK_CACHING}"]
    mrl_opts = [
        f":meta-title={safe_title}",
        f":input-title-format={safe_title}"
    ]
    if audio_only:
        mrl_opts.append(":no-video")
    args += [url] + mrl_opts
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        messagebox.showerror("Erro ao abrir VLC", str(e))

# ---------- yt-dlp helpers ----------
def ydl(extract_flat=True):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True if extract_flat else False,
        "extract_flat": extract_flat,
        "retries": YTDLP_RETRIES,
        "socket_timeout": SOCKET_TIMEOUT,
        "cachedir": True
    }
    if FFMPEG_DIR:
        opts["ffmpeg_location"] = FFMPEG_DIR
    return yt_dlp.YoutubeDL(opts)

def search_youtube_videos(query, limit=10):
    with ydl(extract_flat=True) as y:
        data = y.extract_info(f"ytsearch{limit}:{query}", download=False)
    out = []
    for e in data.get("entries", []) or []:
        out.append({
            "type": "video",
            "id": e.get("id"),
            "title": e.get("title") or "Sem título",
            "url": f"https://www.youtube.com/watch?v={e.get('id')}" if e.get("id") else e.get("url"),
            "duration": e.get("duration_string") or e.get("duration") or "",
            "channel": e.get("uploader") or e.get("channel") or "",
            "thumbnails": e.get("thumbnails") or [],
        })
    return out

def search_youtube_playlists(query, limit=10):
    sp_code = "EgIQAw%3D%3D"  # filtro "Type: Playlist"
    q_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query) + "&sp=" + sp_code
    with ydl(extract_flat=True) as y:
        data = y.extract_info(q_url, download=False)

    entries = data.get("entries", []) or []
    out, seen = [], set()
    for e in entries:
        url = e.get("webpage_url") or e.get("url") or ""
        title = e.get("title") or "Playlist"
        channel = e.get("uploader") or e.get("channel") or ""
        thumbs = e.get("thumbnails") or []
        pid = e.get("id") or ""
        if "list=" not in url.lower() and not (isinstance(pid, str) and pid.startswith("PL")):
            continue
        if "list=" not in url.lower() and pid:
            url = f"https://www.youtube.com/playlist?list={pid}"
        if not url or url in seen:
            continue
        out.append({
            "type": "playlist",
            "id": pid or url,
            "title": title,
            "url": url,
            "channel": channel,
            "thumbnails": thumbs,
        })
        seen.add(url)
        if len(out) >= limit:
            break

    if not out:
        with ydl(extract_flat=True) as y:
            data2 = y.extract_info(f"ytsearch{max(limit, 15)}:{query} playlist", download=False)
        for e in (data2.get("entries", []) or []):
            url2 = e.get("webpage_url") or e.get("url") or ""
            pid2 = e.get("id") or ""
            if "list=" not in url2.lower() and not (isinstance(pid2, str) and pid2.startswith("PL")):
                continue
            if "list=" not in url2.lower() and pid2:
                url2 = f"https://www.youtube.com/playlist?list={pid2}"
            if not url2 or url2 in seen:
                continue
            out.append({
                "type": "playlist",
                "id": pid2 or url2,
                "title": e.get("title") or "Playlist",
                "url": url2,
                "channel": e.get("uploader") or e.get("channel") or "",
                "thumbnails": e.get("thumbnails") or [],
            })
            seen.add(url2)
            if len(out) >= limit:
                break
    return out

def extract_stream_url(video_url, audio_only=True):
    with ydl(extract_flat=False) as y:
        info = y.extract_info(video_url, download=False)
    return info.get("url")

def enqueue_playlist_items(playlist_url, audio_only=True, max_items=PLAYLIST_LIMIT):
    pl_opts = {
        "quiet": True, "no_warnings": True,
        "extract_flat": True, "noplaylist": False,
        "retries": YTDLP_RETRIES, "socket_timeout": SOCKET_TIMEOUT,
        "cachedir": True
    }
    if FFMPEG_DIR:
        pl_opts["ffmpeg_location"] = FFMPEG_DIR
    with yt_dlp.YoutubeDL(pl_opts) as y:
        info = y.extract_info(playlist_url, download=False)

    entries = info.get("entries", []) or []
    count = 0
    for e in entries:
        if count >= max_items:
            break
        vid_url = e.get("url") or (f"https://www.youtube.com/watch?v={e.get('id')}" if e.get("id") else None)
        if not vid_url:
            continue
        title = e.get("title") or "YouTube"
        try:
            stream = extract_stream_url(vid_url, audio_only=audio_only)
            if stream:
                open_in_vlc(stream, title=title, audio_only=audio_only)
                count += 1
        except Exception:
            continue
    return count

# ---------- downloads (Áudio = -x --audio-format mp3) ----------
def _dl_opts_common():
    opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "quiet": False,
        "no_warnings": True,
        "prefer_ffmpeg": True,
        "retries": YTDLP_RETRIES,
        "socket_timeout": SOCKET_TIMEOUT,
        "cachedir": True
    }
    if FFMPEG_DIR:
        opts["ffmpeg_location"] = FFMPEG_DIR
    return opts

def download_media(url, audio_only=True):
    if audio_only and not have_ffmpeg():
        messagebox.showerror("FFmpeg em falta",
                             "Para extrair MP3: coloca ffmpeg/ffprobe em .\\ffmpeg\\bin, no PATH, "
                             "ou define 'ffmpeg_dir' no settings.json.")
        return
    opts = _dl_opts_common()
    opts["noplaylist"] = True

    if audio_only:
        opts.update({
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "postprocessor_args": ["-vn"],
            "format": "bestaudio/best",
        })
    else:
        opts.update({
            "format": "bestvideo*+bestaudio/best",
            "merge_output_format": "mp4",
        })

    def work():
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                y.download([url])
            messagebox.showinfo("Download concluído", f"Guardado em:\n{DOWNLOAD_DIR}")
        except Exception as e:
            messagebox.showerror("Erro no download", str(e))
    threading.Thread(target=work, daemon=True).start()

def download_playlist(playlist_url, audio_only=True, max_items=PLAYLIST_LIMIT):
    if audio_only and not have_ffmpeg():
        messagebox.showerror("FFmpeg em falta",
                             "Para extrair MP3 de playlists: ffmpeg/ffprobe em .\\ffmpeg\\bin, PATH, "
                             "ou 'ffmpeg_dir' no settings.json.")
        return
    opts = _dl_opts_common()
    opts.update({
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(playlist_title)s/%(title)s.%(ext)s"),
        "noplaylist": False,
        "yes_playlist": True,
        "playlistend": max_items,
    })
    if audio_only:
        opts.update({
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "postprocessor_args": ["-vn"],
            "format": "bestaudio/best",
        })
    else:
        opts.update({
            "format": "bestvideo*+bestaudio/best",
            "merge_output_format": "mp4",
        })

    def work():
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                y.download([playlist_url])
            messagebox.showinfo("Download concluído", f"Itens guardados em:\n{DOWNLOAD_DIR}")
        except Exception as e:
            messagebox.showerror("Erro no download da playlist", str(e))
    threading.Thread(target=work, daemon=True).start()

# ---------- thumbnails (corrigido) ----------
def fetch_thumb_img(thumbs):
    """Tenta descarregar a melhor thumbnail e devolve ImageTk.PhotoImage."""
    if not thumbs:
        return None
    ordered = sorted(
        thumbs,
        key=lambda t: (t.get("height", 0) or 0, t.get("width", 0) or 0),
        reverse=True
    )
    for t in ordered:
        url = t.get("url")
        if not url:
            continue
        try:
            r = HTTP.get(url, timeout=SOCKET_TIMEOUT)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            continue
    return None

# ---------- UI (tema escuro) ----------
def apply_dark_theme(root):
    root.configure(bg="#0f0f0f")
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    fg = "#f1f1f1"; bg = "#0f0f0f"; mid = "#1a1a1a"; acc = "#2a2a2a"
    style.configure(".", background=bg, foreground=fg)
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TButton", background=acc, foreground=fg, padding=6, relief="flat")
    style.map("TButton", background=[("active", "#3a3a3a")])
    style.configure("TRadiobutton", background=bg, foreground=fg)
    style.configure("TEntry", fieldbackground=mid, foreground=fg, insertcolor=fg)
    style.configure("TScrollbar", troughcolor=mid, background=acc)
    style.configure("Horizontal.TSeparator", background=acc)
    style.configure("Vertical.TSeparator", background=acc)

# ---------- App ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Search → VLC")
        self.geometry("900x740")
        self.minsize(780, 600)
        apply_dark_theme(self)
        self.search_mode = tk.StringVar(value="music")  # music | playlist
        self.results, self.img_cache = [], {}

        # topo
        top = ttk.Frame(self, padding=12); top.pack(side=tk.TOP, fill=tk.X)
        self.search_entry = ttk.Entry(top, font=("Segoe UI", 12), width=60)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,8))
        self.search_entry.bind("<Return>", self.on_search)
        ttk.Button(top, text="Pesquisar", command=self.on_search).pack(side=tk.LEFT, padx=(0,8))
        mode = ttk.Frame(top); mode.pack(side=tk.LEFT)
        ttk.Radiobutton(mode, text="Music", value="music", variable=self.search_mode).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(mode, text="Playlist", value="playlist", variable=self.search_mode).pack(side=tk.LEFT, padx=4)

        # status
        vlc_status = ("VLC encontrado ✅" if VLC_EXE else "VLC não encontrado ❌ (instala ou define 'vlc_path' em settings.json)")
        ffm_status = ("FFmpeg encontrado ✅ MP3 ativo" if have_ffmpeg() else "FFmpeg/ffprobe não encontrados ❌ (usa .\\ffmpeg\\bin, PATH ou 'ffmpeg_dir')")
        self.status = ttk.Label(self, text=f"{vlc_status}   |   {ffm_status}",
                                font=("Segoe UI", 9), foreground="#9e9e9e")
        self.status.pack(side=tk.TOP, anchor="w", padx=12, pady=(0,6))

        # área de resultados
        wrap = ttk.Frame(self); wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0,12))
        self.canvas = tk.Canvas(wrap, highlightthickness=0, bg="#0f0f0f")
        self.scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.list_frame = ttk.Frame(self.canvas)
        self.item_id = self.canvas.create_window((0,0), window=self.list_frame, anchor="nw")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_cfg)

        self._hint()
        self.after(200, self.search_entry.focus_set)

    def _on_canvas_cfg(self, e): self.canvas.itemconfig(self.item_id, width=e.width)

    def _hint(self):
        for w in self.list_frame.winfo_children(): w.destroy()
        ttk.Label(self.list_frame, text="Pesquisa (Music/Playlist) e Enter — ex.: “lofi hip hop”",
                  font=("Segoe UI", 11), foreground="#cfcfcf").pack(pady=18)

    def on_search(self, *_):
        q = self.search_entry.get().strip()
        if not q: return
        mode = self.search_mode.get()
        self._draw_skeleton(q, mode)

        def work():
            try:
                res = (search_youtube_playlists(q, limit=MAX_RESULTS) if mode == "playlist"
                       else search_youtube_videos(q, limit=MAX_RESULTS))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro na pesquisa", str(e)))
                res = []
            self.after(0, lambda: self._render_results(res))
            with ThreadPoolExecutor(max_workers=THUMB_THREADS) as ex:
                fut = {ex.submit(fetch_thumb_img, it["thumbnails"]): it for it in res}
                for f in as_completed(fut):
                    it = fut[f]
                    try: img = f.result()
                    except: img = None
                    if img: self.img_cache[it["id"]] = img
                    self.after(0, lambda item=it: self._refresh_thumb(item["id"]))
        threading.Thread(target=work, daemon=True).start()

    def _draw_skeleton(self, query, mode):
        for w in self.list_frame.winfo_children(): w.destroy()
        ttk.Label(self.list_frame, text=f"A procurar ({mode}): {query}",
                  font=("Segoe UI", 11), foreground="#cfcfcf").pack(anchor="w", pady=(8,4))
        for _ in range(MAX_RESULTS):
            row = ttk.Frame(self.list_frame); row.pack(fill=tk.X, pady=6)
            # placeholder cinza (substituído pela imagem quando chegar)
            tk.Label(row, bg="#1a1a1a", width=THUMB_W//7, height=THUMB_H//12).pack(side=tk.LEFT, padx=(0,10))
            col = ttk.Frame(row); col.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(col, bg="#2a2a2a", height=1).pack(fill=tk.X, pady=3)
            tk.Label(col, bg="#1f1f1f", height=1).pack(fill=tk.X, pady=3)

    def _render_results(self, results):
        for w in self.list_frame.winfo_children(): w.destroy()
        if not results:
            ttk.Label(self.list_frame, text="Sem resultados.", font=("Segoe UI", 11), foreground="#cfcfcf").pack(pady=18)
            return
        self.results = results
        for item in results:
            self._add_row(item)
        ttk.Label(self.list_frame, text=f"{len(results)} resultados.", foreground="#9e9e9e").pack(anchor="w", pady=4)

    def _add_row(self, item):
        box = ttk.Frame(self.list_frame, padding=(0,6)); box.pack(fill=tk.X)
        row = ttk.Frame(box); row.pack(fill=tk.X)

        # Placeholder imediato + Label da thumb (ainda sem imagem)
        ph = tk.Label(row, bg="#1a1a1a", width=THUMB_W//7, height=THUMB_H//12)
        ph.pack(side=tk.LEFT, padx=(0,10))

        self_thumb = ttk.Label(row, background="#0f0f0f")
        self_thumb._id = item["id"]
        self_thumb._placeholder = ph

        col = ttk.Frame(row); col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(col, text=item["title"], font=("Segoe UI Semibold", 11),
                  foreground="#ffffff", wraplength=560, justify="left").pack(anchor="w")
        meta_bits = []
        if item.get("channel"): meta_bits.append(item["channel"])
        if item.get("duration"): meta_bits.append(str(item["duration"]))
        meta = " • ".join(meta_bits) if meta_bits else ("Playlist" if item["type"] == "playlist" else "")
        ttk.Label(col, text=meta, font=("Segoe UI", 9), foreground="#9e9e9e").pack(anchor="w", pady=(2,0))

        btns = ttk.Frame(row); btns.pack(side=tk.RIGHT)
        if item["type"] == "playlist":
            ttk.Button(btns, text="▶ Áudio (Play All)", command=lambda it=item: self._play_playlist(it, True)).pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)
            ttk.Button(btns, text="▶ Vídeo (Play All)", command=lambda it=item: self._play_playlist(it, False)).pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)
            ttk.Button(btns, text="⬇ Playlist Áudio (MP3)", command=lambda it=item: download_playlist(it["url"], True, PLAYLIST_LIMIT)).pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)
            ttk.Button(btns, text="⬇ Playlist Vídeo", command=lambda it=item: download_playlist(it["url"], False, PLAYLIST_LIMIT)).pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)
        else:
            ttk.Button(btns, text="▶ Áudio", command=lambda it=item: self._play_video(it, True)).pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)
            ttk.Button(btns, text="▶ Vídeo", command=lambda it=item: self._play_video(it, False)).pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)
            ttk.Button(btns, text="⬇ Áudio (MP3)", command=lambda it=item: download_media(it["url"], True)).pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)
            ttk.Button(btns, text="⬇ Vídeo", command=lambda it=item: download_media(it["url"], False)).pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)

        ttk.Separator(self.list_frame, orient="horizontal").pack(fill=tk.X, pady=6)
        item["_thumb_widget"] = self_thumb

    def _refresh_thumb(self, vid):
        for it in self.results:
            if it["id"] == vid and "_thumb_widget" in it:
                w = it["_thumb_widget"]
                img = self.img_cache.get(vid)
                if img:
                    # remove placeholder se existir
                    ph = getattr(w, "_placeholder", None)
                    if ph:
                        try: ph.destroy()
                        except: pass
                        w._placeholder = None
                    # pack da label (se ainda não estiver visível)
                    if not w.winfo_ismapped():
                        w.pack(side=tk.LEFT, padx=(0,10))
                    # aplicar imagem + referência forte para evitar GC
                    w.configure(image=img)
                    w.image = img
                break

    def _play_video(self, item, audio_only):
        def worker():
            try:
                url = extract_stream_url(item["url"], audio_only=audio_only)
                if not url: raise RuntimeError("Stream URL vazio.")
                open_in_vlc(url, title=item.get("title"), audio_only=audio_only)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro ao reproduzir", str(e)))
        threading.Thread(target=worker, daemon=True).start()

    def _play_playlist(self, item, audio_only):
        def worker():
            try:
                n = enqueue_playlist_items(item["url"], audio_only=audio_only, max_items=PLAYLIST_LIMIT)
                if n == 0: raise RuntimeError("Não foi possível obter itens da playlist.")
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro na playlist", str(e)))
        threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    try:
        if platform.system().lower() == "windows":
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    if shutil.which("yt-dlp") is None:
        messagebox.showerror("yt-dlp não encontrado", "Instala com:\npython -m pip install yt-dlp")
        sys.exit(1)

    app = App()
    app.mainloop()
