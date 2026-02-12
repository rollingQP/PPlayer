#!/usr/bin/env python3
"""
PPlayer — privacy-focused FFmpeg video player (no history).
Required : Python 3.7+, Pillow (pip install Pillow)
Optional : tkinterdnd2        (pip install tkinterdnd2) for drag-and-drop
FFmpeg is searched in PATH first, then in ./lib/ beside this script.
"""

import tkinter as tk
from tkinter import ttk, filedialog
import subprocess, threading, time, os, sys, platform, json, queue, shutil, re
from pathlib import Path

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
except ImportError:
    print("Pillow is required:  pip install Pillow")
    sys.exit(1)

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _DND = True
except ImportError:
    _DND = False

_W = platform.system() == "Windows"
try:
    _BIL = Image.Resampling.BILINEAR
except AttributeError:
    _BIL = Image.BILINEAR

# ── Config paths ────────────────────────────────────────────
if _W:
    _CFG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "PPlayer"
else:
    _CFG_DIR = Path.home() / ".pplayer"
_CFG_FILE = _CFG_DIR / "settings.json"

# ━━━━━━━━━━━━━━━━━━━ i18n ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_L = {
    "en": {
        "title": "PPlayer",
        "file": "File",
        "open": "Open File…",
        "open_path": "Open Path / URL…",
        "close": "Close Video",
        "exit": "Exit",
        "playback": "Playback",
        "pp": "Play / Pause",
        "stop": "Stop",
        "bwd5": "Backward 5 s",
        "fwd5": "Forward 5 s",
        "bwd30": "Backward 30 s",
        "fwd30": "Forward 30 s",
        "nf": "Next Frame",
        "fs": "Fullscreen",
        "spd": "Speed",
        "audio": "Audio",
        "vu": "Volume Up",
        "vd": "Volume Down",
        "mute": "Mute / Unmute",
        "settings": "Settings",
        "lang": "Language",
        "boss": "Boss Key…",
        "boss_any": "Any-Key Exit",
        "boss_any_tip": "Press any non-control key to exit",
        "opa": "Opacity",
        "hw": "Hardware Decode",
        "hwa": "Auto",
        "hwd": "Disabled",
        "sub": "Subtitle",
        "sub_off": "Off",
        "sub_ext": "Load External…",
        "help": "Help",
        "about": "About",
        "abt": (
            "PPlayer\n"
            "FFmpeg-based video player\n"
            "No playback history is ever recorded.\n\n"
            "This software uses FFmpeg, a complete cross-platform\n"
            "solution to record, convert and stream audio and video.\n"
            "FFmpeg is free software licensed under the LGPL/GPL.\n"
            "Copyright (c) the FFmpeg developers.\n"
            "https://ffmpeg.org  |  https://ffmpeg.org/legal.html"
        ),
        "hint": "Drop a video file here\nor use  File → Open",
        "hint_nodnd": "Use  File → Open  to play a video",
        "htag": "HW: {}",
        "stag": "SW Decode",
        "noff": "FFmpeg not found!\nInstall FFmpeg or place binaries in ./lib/",
        "ep": "Enter file path or URL:",
        "bp": "Press a key to set as new boss key.\nCurrent: {}",
        "eo": "Cannot open:\n{}",
        "ok": "OK",
        "cancel": "Cancel",
    },
    "zh": {
        "title": "PPlayer",
        "file": "文件",
        "open": "打开文件…",
        "open_path": "打开路径/URL…",
        "close": "关闭视频",
        "exit": "退出",
        "playback": "播放",
        "pp": "播放/暂停",
        "stop": "停止",
        "bwd5": "后退 5 秒",
        "fwd5": "快进 5 秒",
        "bwd30": "后退 30 秒",
        "fwd30": "快进 30 秒",
        "nf": "下一帧",
        "fs": "全屏",
        "spd": "速度",
        "audio": "音频",
        "vu": "音量 +",
        "vd": "音量 −",
        "mute": "静音/取消静音",
        "settings": "设置",
        "lang": "语言",
        "boss": "老板键…",
        "boss_any": "任意键退出",
        "boss_any_tip": "按任意非控制键退出",
        "opa": "透明度",
        "hw": "硬件解码",
        "hwa": "自动",
        "hwd": "禁用",
        "sub": "字幕",
        "sub_off": "关闭",
        "sub_ext": "加载外部字幕…",
        "help": "帮助",
        "about": "关于",
        "abt": (
            "PPlayer\n"
            "基于 FFmpeg 的视频播放器\n"
            "不记录任何播放历史。\n\n"
            "本软件使用 FFmpeg —— 完整的跨平台音视频\n"
            "录制、转换与流媒体解决方案。\n"
            "FFmpeg 是基于 LGPL/GPL 许可的自由软件。\n"
            "Copyright (c) FFmpeg 开发者。\n"
            "https://ffmpeg.org  |  https://ffmpeg.org/legal.html"
        ),
        "hint": "拖放视频文件到此处\n或使用  文件→打开",
        "hint_nodnd": "使用  文件→打开  来播放视频",
        "htag": "硬解: {}",
        "stag": "软件解码",
        "noff": "未找到 FFmpeg！\n请安装 FFmpeg 或将其放入 ./lib/ 目录",
        "ep": "输入文件路径或 URL：",
        "bp": "按下一个键设为新的老板键\n当前：{}",
        "eo": "无法打开：\n{}",
        "ok": "确定",
        "cancel": "取消",
    },
}


# ━━━━━━━━━━━━━━━ FFmpeg helpers ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _find(name):
    p = shutil.which(name)
    if p:
        return p
    lib = Path(os.path.dirname(os.path.abspath(sys.argv[0]))) / "lib"
    c = lib / (f"{name}.exe" if _W else name)
    if c.is_file():
        return str(c)
    return None


def _pkw():
    kw = {}
    if _W:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kw["startupinfo"] = si
        kw["creationflags"] = 0x08000000
    return kw


def _run_text(cmd, timeout=15):
    try:
        r = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, **_pkw())
        return r.stdout.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _run_bin(cmd, timeout=5):
    try:
        r = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, **_pkw())
        return r.stdout
    except Exception:
        return b""


def _probe(ffprobe, path):
    txt = _run_text(
        [ffprobe, "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", path], timeout=15)
    if not txt:
        return None
    try:
        d = json.loads(txt)
    except json.JSONDecodeError:
        return None
    info = dict(duration=0.0, width=0, height=0, fps=30.0,
                has_audio=False, vcodec="", subs=[])
    info["duration"] = float(d.get("format", {}).get("duration", 0))
    sub_idx = 0
    for s in d.get("streams", []):
        ct = s.get("codec_type")
        if ct == "video" and info["width"] == 0:
            info["width"] = int(s.get("width", 0))
            info["height"] = int(s.get("height", 0))
            info["vcodec"] = s.get("codec_name", "")
            try:
                fr = s.get("r_frame_rate", "30/1")
                if "/" in fr:
                    n, dd = fr.split("/")
                    info["fps"] = float(n) / max(1, float(dd))
                else:
                    info["fps"] = float(fr)
            except (ValueError, ZeroDivisionError):
                pass
            if not (0 < info["fps"] <= 240):
                info["fps"] = 30.0
        elif ct == "audio":
            info["has_audio"] = True
        elif ct == "subtitle":
            tags = s.get("tags", {})
            lang = tags.get("language", tags.get("title", f"#{sub_idx}"))
            title = tags.get("title", "")
            label = f"#{sub_idx}"
            if title:
                label += f" {title}"
            if lang and lang != title:
                label += f" ({lang})"
            info["subs"].append({
                "index": int(s.get("index", sub_idx)),
                "stream_idx": sub_idx,
                "label": label,
                "codec": s.get("codec_name", ""),
            })
            sub_idx += 1
    return info if info["width"] > 0 else None


def _hwaccels(ffmpeg):
    txt = _run_text([ffmpeg, "-hwaccels"], timeout=5)
    lines = txt.strip().split("\n")
    return [l.strip() for l in lines[1:] if l.strip()]


def _read_n(pipe, n):
    buf = b""
    while len(buf) < n:
        ch = pipe.read(n - len(buf))
        if not ch:
            return None
        buf += ch
    return buf


# ━━━━━━━━━━━━━━━ Audio Player (master clock) ━━━━━━━━━━━━━━━
class _AudioPlayer:
    """Wraps ffplay; reads stderr in real-time to track audio position."""

    def __init__(self):
        self._proc = None
        self._pos = 0.0
        self._pos_wall = 0.0
        self._seek_time = 0.0
        self._speed = 1.0
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._alive = False

    # ── public API ──────────────────────────────────────
    def start(self, ffplay_path, file_path, seek_time, volume, speed):
        self.stop()
        self._speed = max(0.1, speed)
        self._seek_time = seek_time
        with self._lock:
            self._pos = seek_time
            self._pos_wall = time.monotonic()
        self._ready.clear()
        self._alive = True

        cmd = [ffplay_path, "-nodisp", "-autoexit", "-vn",
               "-loglevel", "info"]
        if seek_time > 0.5:
            cmd += ["-ss", f"{seek_time:.3f}"]
        cmd += ["-volume", str(volume)]
        if abs(speed - 1.0) > 0.01:
            parts = []
            v = speed
            while v > 2.0:
                parts.append("atempo=2.0")
                v /= 2.0
            while v < 0.5:
                parts.append("atempo=0.5")
                v *= 2.0
            parts.append(f"atempo={v:.4f}")
            cmd += ["-af", ",".join(parts)]
        cmd += ["-i", file_path]

        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                **_pkw())
        except Exception:
            self._alive = False
            return
        threading.Thread(target=self._reader, daemon=True).start()

    def stop(self):
        self._alive = False
        self._ready.clear()
        proc = self._proc
        self._proc = None
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def wait_ready(self, timeout=5.0):
        return self._ready.wait(timeout)

    @property
    def is_ready(self):
        return self._ready.is_set()

    @property
    def is_alive(self):
        return (self._alive and self._proc is not None
                and self._proc.poll() is None)

    @property
    def media_position(self):
        """Estimated current media-time (interpolated between reports)."""
        with self._lock:
            if not self._ready.is_set():
                return self._seek_time
            elapsed = time.monotonic() - self._pos_wall
            # ffplay output-time advances at 1× real-time even with atempo
            interp = self._pos + elapsed
            if abs(self._speed - 1.0) < 0.01:
                return interp
            # convert output-time → media-time for non-1× speed
            return self._seek_time + (interp - self._seek_time) * self._speed

    # ── internal ────────────────────────────────────────
    def _reader(self):
        proc = self._proc
        if not proc:
            return
        buf = b""
        try:
            while proc.poll() is None:
                ch = proc.stderr.read(1)
                if not ch:
                    break
                if ch in (b'\r', b'\n'):
                    if buf:
                        self._parse(buf.decode("utf-8", errors="ignore"))
                        buf = b""
                else:
                    buf += ch
                    if len(buf) > 1024:
                        buf = b""
        except (OSError, ValueError):
            pass
        self._alive = False

    _RE_STATUS = re.compile(r'([\d]+\.[\d]+).*?fd=')

    def _parse(self, line):
        m = self._RE_STATUS.search(line)
        if m:
            try:
                pos = float(m.group(1))
                with self._lock:
                    self._pos = pos
                    self._pos_wall = time.monotonic()
                if not self._ready.is_set():
                    self._ready.set()
            except ValueError:
                pass


# ━━━━━━━━━━━━━━━ Widgets ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _VCanvas(tk.Canvas):
    def __init__(self, master, **kw):
        kw.setdefault("bg", "black")
        kw.setdefault("highlightthickness", 0)
        super().__init__(master, **kw)
        self._ph = None

    def show_img(self, pil):
        cw, ch = self.winfo_width(), self.winfo_height()
        if cw < 2 or ch < 2:
            return
        iw, ih = pil.size
        s = min(cw / iw, ch / ih)
        nw, nh = max(1, int(iw * s)), max(1, int(ih * s))
        self._ph = ImageTk.PhotoImage(pil.resize((nw, nh), _BIL))
        self.delete("all")
        self.create_image(cw // 2, ch // 2, image=self._ph, anchor="center")

    def show_txt(self, txt):
        self.delete("all")
        cw, ch = self.winfo_width(), self.winfo_height()
        if cw > 1:
            self.create_text(cw // 2, ch // 2, text=txt,
                             fill="#555", font=("Helvetica", 16),
                             justify="center")


class _Bar(tk.Canvas):
    def __init__(self, master, **kw):
        super().__init__(master, height=24, bg="#181818",
                         highlightthickness=0, **kw)
        self.dur = 0.0
        self.pos = 0.0
        self._drag = False
        self.on_seek = None
        self.on_drag_start = None
        self.on_drag_pos = None
        self.on_hover = None
        self.on_leave_cb = None
        self.bind("<Button-1>", self._b1)
        self.bind("<B1-Motion>", self._bm)
        self.bind("<ButtonRelease-1>", self._br)
        self.bind("<Motion>", self._mv)
        self.bind("<Leave>", self._lv)
        self.bind("<Configure>", lambda e: self._draw())

    def _t(self, x):
        w = self.winfo_width()
        if self.dur <= 0 or w <= 0:
            return 0.0
        return max(0.0, min(self.dur, x / w * self.dur))

    def _x(self, t):
        w = self.winfo_width()
        return (t / self.dur * w) if self.dur > 0 else 0

    def set_pos(self, t):
        if not self._drag:
            self.pos = t
            self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        cy = h // 2
        self.create_rectangle(4, cy - 3, w - 4, cy + 3,
                              fill="#444", outline="")
        if self.dur > 0:
            px = max(4, min(w - 4, self._x(self.pos)))
            self.create_rectangle(4, cy - 3, px, cy + 3,
                                  fill="#0078d4", outline="")
            self.create_oval(px - 6, cy - 6, px + 6, cy + 6,
                             fill="white", outline="#0078d4", width=2)

    def _b1(self, e):
        self._drag = True
        self.pos = self._t(e.x)
        self._draw()
        if self.on_drag_start:
            self.on_drag_start()
        if self.on_leave_cb:
            self.on_leave_cb()
        if self.on_drag_pos:
            self.on_drag_pos(self.pos)

    def _bm(self, e):
        if self._drag:
            self.pos = self._t(e.x)
            self._draw()
            if self.on_drag_pos:
                self.on_drag_pos(self.pos)

    def _br(self, e):
        if self._drag:
            self._drag = False
            self.pos = self._t(e.x)
            self._draw()
            if self.on_seek:
                self.on_seek(self.pos)

    def _mv(self, e):
        if self._drag:
            return
        t = self._t(e.x)
        if self.on_hover and self.dur > 0:
            self.on_hover(t, self.winfo_rootx() + e.x,
                          self.winfo_rooty())

    def _lv(self, e):
        if self.on_leave_cb:
            self.on_leave_cb()


class _Tip:
    def __init__(self, par):
        self._par = par
        self._w = None
        self._ph = None
        self._il = None
        self._tl = None

    def show(self, pil, txt, sx, sy):
        if self._w is None:
            self._w = tk.Toplevel(self._par)
            self._w.overrideredirect(True)
            self._w.attributes("-topmost", True)
            self._il = tk.Label(self._w, bg="black", bd=1, relief="solid")
            self._il.pack()
            self._tl = tk.Label(self._w, bg="black", fg="white",
                                font=("Helvetica", 9))
            self._tl.pack()
        self._ph = ImageTk.PhotoImage(pil)
        self._il.config(image=self._ph)
        self._tl.config(text=txt)
        iw, ih = pil.size
        nx = max(0, sx - iw // 2)
        ny = max(0, sy - ih - 40)
        self._w.geometry(f"+{nx}+{ny}")
        self._w.deiconify()

    def hide(self):
        if self._w:
            self._w.withdraw()

    def destroy(self):
        if self._w:
            self._w.destroy()
            self._w = None


# ━━━━━━━━━━━━━━━━━━ Player ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Player:
    SPEEDS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]

    _CONTROL_KEYS = {
        "space", "Left", "Right", "Up", "Down",
        "m", "M", "f", "F", "F11", "period",
        "bracketleft", "bracketright",
        "Return", "Tab", "Shift_L", "Shift_R",
        "Control_L", "Control_R", "Alt_L", "Alt_R",
        "Super_L", "Super_R", "Caps_Lock", "Num_Lock",
        "Scroll_Lock", "Menu", "Pause", "Print",
        "F1", "F2", "F3", "F4", "F5", "F6",
        "F7", "F8", "F9", "F10", "F12",
    }

    def __init__(self):
        self._ff = _find("ffmpeg")
        self._fp = _find("ffprobe")
        self._fy = _find("ffplay")

        # ── load persisted settings ─────────────────────
        cfg = self._load_settings()
        self._lang = cfg["lang"]
        self._vol = cfg["volume"]
        self._speed = cfg["speed"]
        self._hwm = cfg["hw_mode"]
        self._boss = cfg["boss_key"]
        self._boss_any = cfg["boss_any"]
        self._opacity = cfg["opacity"]
        self._saved_geo = cfg["geometry"]

        self._path = None
        self._info = None
        self._playing = False
        self._paused = False
        self._ct = 0.0
        self._muted = False
        self._fsc = False
        self._gen = 0
        self._evt = threading.Event()
        self._q = queue.Queue(maxsize=8)
        self._vp = None
        self._audio = _AudioPlayer()
        self._frame = None
        self._dw = 0
        self._dh = 0
        self._pcache = {}
        self._pbusy = False
        self._ui_ready = False
        self._click_pending = None
        self._drag_gen = 0
        self._drag_busy = False
        self._drag_was_playing = False
        self._vol_timer = None
        self._hwd = ""
        self._sync_t0 = 0.0

        self._sub_mode = "off"
        self._sub_ext_path = None

        self._root = TkinterDnD.Tk() if _DND else tk.Tk()
        self._root.title("PPlayer")
        self._root.geometry(self._saved_geo)
        self._root.minsize(480, 320)
        self._root.configure(bg="black")
        self._root.attributes("-alpha", self._opacity)

        if not self._ff:
            self._root.withdraw()
            from tkinter import messagebox
            messagebox.showerror("Error", _L[self._lang]["noff"])
            sys.exit(1)

        self._build_ui()
        self._ui_ready = True
        self._build_menus()
        self._bind_keys()

        # apply loaded settings to UI widgets
        self._vsc.set(self._vol)
        self._lsp.config(text=f"{self._speed}x")
        self._mu_icon()

        if _DND:
            self._root.drop_target_register(DND_FILES)
            self._root.dnd_bind("<<Drop>>", self._on_drop)

        self._root.after(250, self._show_hint)
        self._tick()

    def run(self):
        self._root.mainloop()

    # ── i18n helper ─────────────────────────────────────
    def _S(self, k):
        return _L.get(self._lang, _L["en"]).get(k, k)

    @staticmethod
    def _fmt(s):
        s = max(0, int(s))
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"

    def _show_hint(self):
        key = "hint" if _DND else "hint_nodnd"
        self._cv.show_txt(self._S(key))

    # ━━━━━━━━━━━━━ Settings persistence ━━━━━━━━━━━━━━━━
    def _load_settings(self):
        defaults = dict(lang="en", volume=100, speed=1.0,
                        hw_mode="auto", boss_key="Escape",
                        boss_any=False, opacity=1.0,
                        geometry="960x600")
        try:
            if _CFG_FILE.exists():
                with open(_CFG_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                for k in defaults:
                    if k in d:
                        defaults[k] = d[k]
        except Exception:
            pass
        # validate
        if defaults["lang"] not in _L:
            defaults["lang"] = "en"
        defaults["volume"] = max(0, min(100, int(defaults["volume"])))
        if defaults["speed"] not in Player.SPEEDS:
            defaults["speed"] = 1.0
        defaults["opacity"] = max(0.3, min(1.0, float(defaults["opacity"])))
        if not isinstance(defaults["boss_any"], bool):
            defaults["boss_any"] = False
        if not isinstance(defaults["geometry"], str):
            defaults["geometry"] = "960x600"
        return defaults

    def _save_settings(self):
        try:
            _CFG_DIR.mkdir(parents=True, exist_ok=True)
            geo = "960x600"
            try:
                geo = self._root.geometry()
            except Exception:
                pass
            d = dict(lang=self._lang, volume=self._vol,
                     speed=self._speed, hw_mode=self._hwm,
                     boss_key=self._boss, boss_any=self._boss_any,
                     opacity=self._opacity, geometry=geo)
            with open(_CFG_FILE, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ━━━━━━━━━━━━━━━━━ Build UI ━━━━━━━━━━━━━━━━━━━━━━━━
    def _build_ui(self):
        self._mb = tk.Menu(self._root)
        self._root.config(menu=self._mb)

        self._mf = tk.Menu(self._mb, tearoff=0)
        self._mp = tk.Menu(self._mb, tearoff=0)
        self._ma = tk.Menu(self._mb, tearoff=0)
        self._ms = tk.Menu(self._mb, tearoff=0)
        self._mh = tk.Menu(self._mb, tearoff=0)
        self._msp = tk.Menu(self._mp, tearoff=0)
        self._ml = tk.Menu(self._ms, tearoff=0)
        self._mhw = tk.Menu(self._ms, tearoff=0)
        self._mop = tk.Menu(self._ms, tearoff=0)
        self._msub = tk.Menu(self._mb, tearoff=0)

        self._mb.add_cascade(label="File", menu=self._mf)
        self._mb.add_cascade(label="Playback", menu=self._mp)
        self._mb.add_cascade(label="Audio", menu=self._ma)
        self._mb.add_cascade(label="Subtitle", menu=self._msub)
        self._mb.add_cascade(label="Settings", menu=self._ms)
        self._mb.add_cascade(label="Help", menu=self._mh)

        self._cv = _VCanvas(self._root)
        self._cv.pack(fill="both", expand=True)
        self._cv.bind("<Double-1>", self._on_dbl_click)
        self._cv.bind("<Button-1>", self._on_single_click)
        self._cv.bind("<MouseWheel>",
                      lambda e: self._chg_vol(5 if e.delta > 0 else -5))
        self._cv.bind("<Button-4>", lambda e: self._chg_vol(5))
        self._cv.bind("<Button-5>", lambda e: self._chg_vol(-5))

        ctrl = tk.Frame(self._root, bg="#181818", height=64)
        ctrl.pack(fill="x", side="bottom")
        ctrl.pack_propagate(False)
        self._ctrl = ctrl

        self._bar = _Bar(ctrl)
        self._bar.pack(fill="x", padx=4, pady=(4, 0))
        self._bar.on_seek = self._on_bar_release
        self._bar.on_drag_start = self._on_drag_start
        self._bar.on_drag_pos = self._on_drag_preview
        self._bar.on_hover = self._prev_hover
        self._bar.on_leave_cb = self._prev_leave
        self._tip = _Tip(self._root)

        bf = tk.Frame(ctrl, bg="#181818")
        bf.pack(fill="x", padx=4)

        B = dict(bg="#181818", fg="white", bd=0,
                 activebackground="#333", activeforeground="white",
                 font=("Segoe UI Symbol", 12), padx=6)

        self._bpp = tk.Button(bf, text="\u25B6",
                              command=self._toggle_play, **B)
        self._bpp.pack(side="left")

        tk.Button(bf, text="\u23F9",
                  command=self._do_stop, **B).pack(side="left")

        self._tv = tk.StringVar(value="00:00 / 00:00")
        tk.Label(bf, textvariable=self._tv, bg="#181818", fg="#aaa",
                 font=("Consolas", 10)).pack(side="left", padx=8)

        self._lhw = tk.Label(bf, text="", bg="#181818", fg="#6a6",
                             font=("Helvetica", 9))
        self._lhw.pack(side="right", padx=4)

        self._lsp = tk.Label(bf, text="1.0x", bg="#181818", fg="#aaa",
                             font=("Helvetica", 9))
        self._lsp.pack(side="right", padx=4)

        vf = tk.Frame(bf, bg="#181818")
        vf.pack(side="right")

        self._bmu = tk.Button(vf, text="\U0001F50A",
                              command=self._toggle_mute, **B)
        self._bmu.pack(side="left")

        self._lvl = tk.Label(vf, text="100%", bg="#181818", fg="#aaa",
                             font=("Helvetica", 9), width=5)
        self._lvl.pack(side="right")

        self._vsc = ttk.Scale(vf, from_=0, to=100, orient="horizontal",
                              length=80, command=self._on_vol)
        self._vsc.set(self._vol)
        self._vsc.pack(side="left")

    def _on_single_click(self, event):
        self._cv.focus_set()
        if self._click_pending is not None:
            self._root.after_cancel(self._click_pending)
        self._click_pending = self._root.after(300, self._do_delayed_click)

    def _on_dbl_click(self, event):
        if self._click_pending is not None:
            self._root.after_cancel(self._click_pending)
            self._click_pending = None
        self._toggle_fs()

    def _do_delayed_click(self):
        self._click_pending = None
        self._toggle_play()

    # ━━━━━━━━━━━━━━━ Populate Menus ━━━━━━━━━━━━━━━━━━━
    def _build_menus(self):
        S = self._S

        self._mb.entryconfigure(1, label=S("file"))
        self._mb.entryconfigure(2, label=S("playback"))
        self._mb.entryconfigure(3, label=S("audio"))
        self._mb.entryconfigure(4, label=S("sub"))
        self._mb.entryconfigure(5, label=S("settings"))
        self._mb.entryconfigure(6, label=S("help"))

        for m in (self._mf, self._mp, self._ma, self._ms,
                  self._mh, self._msp, self._ml, self._mhw,
                  self._mop, self._msub):
            m.delete(0, "end")

        self._mf.add_command(label=S("open"), accelerator="Ctrl+O",
                             command=self._open_file)
        self._mf.add_command(label=S("open_path"), accelerator="Ctrl+L",
                             command=self._open_path)
        self._mf.add_separator()
        self._mf.add_command(label=S("close"), command=self._do_close)
        self._mf.add_separator()
        self._mf.add_command(label=S("exit"), command=self._quit)

        self._mp.add_command(label=S("pp"), accelerator="Space",
                             command=self._toggle_play)
        self._mp.add_command(label=S("stop"), command=self._do_stop)
        self._mp.add_separator()
        self._mp.add_command(label=S("bwd5"), accelerator="\u2190",
                             command=lambda: self._seek_rel(-5))
        self._mp.add_command(label=S("fwd5"), accelerator="\u2192",
                             command=lambda: self._seek_rel(5))
        self._mp.add_command(label=S("bwd30"), accelerator="Ctrl+\u2190",
                             command=lambda: self._seek_rel(-30))
        self._mp.add_command(label=S("fwd30"), accelerator="Ctrl+\u2192",
                             command=lambda: self._seek_rel(30))
        self._mp.add_command(label=S("nf"), accelerator=".",
                             command=self._next_frame)
        self._mp.add_separator()
        for s in self.SPEEDS:
            self._msp.add_command(
                label=f"{s}x",
                command=lambda v=s: self._set_speed(v))
        self._mp.add_cascade(label=S("spd"), menu=self._msp)
        self._mp.add_separator()
        self._mp.add_command(label=S("fs"), accelerator="F / F11",
                             command=self._toggle_fs)

        self._ma.add_command(label=S("vu"), accelerator="\u2191",
                             command=lambda: self._chg_vol(5))
        self._ma.add_command(label=S("vd"), accelerator="\u2193",
                             command=lambda: self._chg_vol(-5))
        self._ma.add_command(label=S("mute"), accelerator="M",
                             command=self._toggle_mute)

        # subtitle menu
        self._msub.add_command(label=S("sub_off"),
                               command=self._sub_off)
        self._msub.add_separator()
        if self._info and self._info.get("subs"):
            for sub in self._info["subs"]:
                si = sub["stream_idx"]
                self._msub.add_command(
                    label=sub["label"],
                    command=lambda idx=si: self._sub_embed(idx))
            self._msub.add_separator()
        self._msub.add_command(label=S("sub_ext"),
                               command=self._sub_load_ext)

        self._ml.add_command(label="English",
                             command=lambda: self._set_lang("en"))
        self._ml.add_command(label="\u4E2D\u6587",
                             command=lambda: self._set_lang("zh"))
        self._ms.add_cascade(label=S("lang"), menu=self._ml)

        self._ms.add_command(label=S("boss"), command=self._set_boss)

        self._boss_any_var = tk.BooleanVar(value=self._boss_any)
        self._ms.add_checkbutton(
            label=S("boss_any"),
            variable=self._boss_any_var,
            command=self._toggle_boss_any)

        self._mhw.add_command(label=S("hwa"),
                              command=lambda: self._set_hw("auto"))
        self._mhw.add_command(label=S("hwd"),
                              command=lambda: self._set_hw("off"))
        for a in _hwaccels(self._ff):
            self._mhw.add_command(
                label=a, command=lambda v=a: self._set_hw(v))
        self._ms.add_cascade(label=S("hw"), menu=self._mhw)

        for p in (100, 90, 80, 70, 60, 50, 40, 30):
            self._mop.add_command(
                label=f"{p}%",
                command=lambda v=p: self._set_opacity(v))
        self._ms.add_cascade(label=S("opa"), menu=self._mop)

        self._mh.add_command(label=S("about"), command=self._about)

    def _set_opacity(self, pct):
        self._opacity = max(0.3, min(1.0, pct / 100.0))
        self._root.attributes("-alpha", self._opacity)

    # ━━━━━━━━━━━━━━━ Key Bindings ━━━━━━━━━━━━━━━━━━━━━
    def _bind_keys(self):
        r = self._root
        r.bind("<space>", lambda e: self._toggle_play())
        r.bind("<Left>", lambda e: self._seek_rel(-5))
        r.bind("<Right>", lambda e: self._seek_rel(5))
        r.bind("<Control-Left>", lambda e: self._seek_rel(-30))
        r.bind("<Control-Right>", lambda e: self._seek_rel(30))
        r.bind("<Up>", lambda e: self._chg_vol(5))
        r.bind("<Down>", lambda e: self._chg_vol(-5))
        r.bind("<m>", lambda e: self._toggle_mute())
        r.bind("<M>", lambda e: self._toggle_mute())
        r.bind("<f>", lambda e: self._toggle_fs())
        r.bind("<F>", lambda e: self._toggle_fs())
        r.bind("<F11>", lambda e: self._toggle_fs())
        r.bind("<Control-o>", lambda e: self._open_file())
        r.bind("<Control-O>", lambda e: self._open_file())
        r.bind("<Control-l>", lambda e: self._open_path())
        r.bind("<Control-L>", lambda e: self._open_path())
        r.bind("<period>", lambda e: self._next_frame())
        r.bind("<bracketright>", lambda e: self._cycle_speed(1))
        r.bind("<bracketleft>", lambda e: self._cycle_speed(-1))
        r.bind("<Key>", self._on_any_key)
        r.protocol("WM_DELETE_WINDOW", self._quit)

    def _on_any_key(self, event):
        ks = event.keysym
        if ks == self._boss:
            self._quit()
            return "break"
        if self._boss_any and ks not in self._CONTROL_KEYS:
            if not (event.state & 0x4):
                self._quit()
                return "break"
        return None

    def _toggle_boss_any(self):
        self._boss_any = self._boss_any_var.get()

    # ━━━━━━━━━━━━━━━ Language ━━━━━━━━━━━━━━━━━━━━━━━━━
    def _set_lang(self, c):
        self._lang = c
        self._apply_lang()
        if not self._playing and not self._path:
            self._show_hint()

    def _apply_lang(self):
        self._root.title(
            f"{os.path.basename(self._path)} — {self._S('title')}"
            if self._path else self._S("title"))
        self._build_menus()

    # ━━━━━━━━━━━━━ Drag and Drop ━━━━━━━━━━━━━━━━━━━━━━
    def _on_drop(self, event):
        p = event.data.strip()
        if p.startswith("{"):
            p = p[1:]
        if p.endswith("}"):
            p = p[:-1]
        p = p.split("\n")[0].strip().strip("'\"")
        if p:
            self._open_video(p)

    # ━━━━━━━━━━━━━ File Dialogs ━━━━━━━━━━━━━━━━━━━━━━━
    def _open_file(self):
        ft = [("Video",
               "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v "
               "*.ts *.mpg *.mpeg *.3gp *.ogv *.rmvb *.rm *.vob"),
              ("All", "*.*")]
        p = filedialog.askopenfilename(filetypes=ft)
        if p:
            self._open_video(p)

    def _open_path(self):
        dlg = tk.Toplevel(self._root)
        dlg.title(self._S("open_path"))
        dlg.geometry("520x120")
        dlg.transient(self._root)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text=self._S("ep"),
                 font=("Helvetica", 10)).pack(padx=10, pady=(10, 4),
                                              anchor="w")
        ent = tk.Entry(dlg, font=("Helvetica", 11))
        ent.pack(padx=10, fill="x")
        ent.focus_set()

        res = [None]

        def ok():
            res[0] = ent.get().strip()
            dlg.destroy()

        ent.bind("<Return>", lambda e: ok())
        ent.bind("<Escape>", lambda e: dlg.destroy())

        fr = tk.Frame(dlg)
        fr.pack(pady=8)
        tk.Button(fr, text=self._S("ok"), width=10,
                  command=ok).pack(side="left", padx=4)
        tk.Button(fr, text=self._S("cancel"), width=10,
                  command=dlg.destroy).pack(side="left", padx=4)

        dlg.wait_window()
        if res[0]:
            self._open_video(res[0])

    # ━━━━━━━━━━━━━ Subtitle ━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _sub_off(self):
        changed = self._sub_mode != "off"
        self._sub_mode = "off"
        self._sub_ext_path = None
        if changed and self._playing:
            t = self._ct
            self._kill()
            self._start(t)

    def _sub_embed(self, stream_idx):
        new_mode = f"embed:{stream_idx}"
        changed = self._sub_mode != new_mode
        self._sub_mode = new_mode
        self._sub_ext_path = None
        if changed and self._playing:
            t = self._ct
            self._kill()
            self._start(t)
        elif changed and self._paused:
            self._grab_frame(self._ct)

    def _sub_load_ext(self):
        ft = [("Subtitle",
               "*.srt *.ass *.ssa *.sub *.vtt *.idx *.sup"),
              ("All", "*.*")]
        p = filedialog.askopenfilename(filetypes=ft)
        if p:
            self._sub_mode = "ext"
            self._sub_ext_path = p
            if self._playing:
                t = self._ct
                self._kill()
                self._start(t)
            elif self._paused:
                self._grab_frame(self._ct)

    def _build_vf_filter(self):
        parts = []
        if self._sub_mode.startswith("embed:"):
            idx = int(self._sub_mode.split(":")[1])
            if self._path:
                # 1. 将反斜杠替换为正斜杠，避免转义歧义
                safe = self._path.replace("\\", "/")
                # 2. 关键修复：在 Windows 上，必须转义驱动器后的冒号 (C: -> C\:)
                #    注意这里只用一个反斜杠转义 (Python字符串写作 "\\:")
                safe = safe.replace(":", "\\:")
                # 3. 转义文件名内部的单引号
                safe = safe.replace("'", "\\'")
                # 注意：不要转义 [ 或 ]，也不要使用双重反斜杠转义冒号
                
                parts.append(f"subtitles='{safe}':si={idx}")
        elif self._sub_mode == "ext" and self._sub_ext_path:
            safe = self._sub_ext_path.replace("\\", "/")
            safe = safe.replace(":", "\\:")
            safe = safe.replace("'", "\\'")
            parts.append(f"subtitles='{safe}'")
            
        parts.append(f"scale={self._dw}:{self._dh}")
        return ",".join(parts)



    # ━━━━━━━━━━━━━ Open Video ━━━━━━━━━━━━━━━━━━━━━━━━━
    def _open_video(self, path):
        self._do_close()
        if not self._fp:
            return
        info = _probe(self._fp, path)
        if info is None:
            self._alert(self._S("eo").format(path))
            return
        self._path = path
        self._info = info
        self._ct = 0.0
        self._bar.dur = info["duration"]
        self._bar.set_pos(0)
        self._pcache.clear()
        self._sub_mode = "off"
        self._sub_ext_path = None

        w, h = info["width"], info["height"]
        if h > 1080:
            w = int(w * 1080 / h)
            h = 1080
        self._dw = w + (w % 2)
        self._dh = h + (h % 2)

        self._root.title(
            f"{os.path.basename(path)} — {self._S('title')}")
        self._build_menus()
        self._start(0.0)

    # ━━━━━━━━━━━━━━━━ Playback Engine ━━━━━━━━━━━━━━━━━
    def _start(self, t):
        self._evt.clear()
        self._gen += 1
        gen = self._gen
        self._playing = True
        self._paused = False
        self._ct = t
        self._hwd = ""
        self._lhw.config(text="")

        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

        # ── video process ───────────────────────────────
        cmd = [self._ff]
        if self._hwm == "auto":
            cmd += ["-hwaccel", "auto"]
        elif self._hwm != "off":
            cmd += ["-hwaccel", self._hwm]
        
        if t > 0.5:
            cmd += ["-ss", f"{t:.3f}"]

        # 【修复关键点】：添加 -copyts 参数
        # 这保留了原始时间戳，确保字幕滤镜能正确匹配视频帧
        cmd += ["-copyts"]

        cmd += ["-i", self._path]

        vf = self._build_vf_filter()
        cmd += ["-vf", vf]
        cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24",
                "-an", "-sn",
                "-v", "error", "pipe:1"]
        try:
            self._vp = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                bufsize=self._dw * self._dh * 3 * 2,
                **_pkw())
        except Exception as exc:
            self._alert(str(exc))
            self._playing = False
            return

        # ── audio process (master clock) ────────────────
        if self._info["has_audio"] and self._fy and not self._muted:
            self._audio.start(self._fy, self._path,
                              t, self._vol, self._speed)

        self._sync_t0 = t

        threading.Thread(target=self._vloop, args=(gen,),
                         daemon=True).start()
        threading.Thread(target=self._detect_hw_thread, args=(gen,),
                         daemon=True).start()
        self._bpp.config(text="\u23F8")

    def _kill(self):
        self._evt.set()
        self._playing = False
        self._audio.stop()
        p = self._vp
        if p:
            self._vp = None
            try:
                p.kill()
            except Exception:
                pass
            try:
                p.stdout.close()
            except Exception:
                pass
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    # ── video reader thread (syncs to audio clock) ─────
    def _vloop(self, gen):
        proc = self._vp
        if not proc:
            return
        fsz = self._dw * self._dh * 3
        fps = self._info["fps"]
        spf = 1.0 / fps
        speed = max(0.1, self._speed)
        dspf = spf / speed            # wall-seconds per frame

        t0 = self._sync_t0
        has_audio = (self._info["has_audio"] and not self._muted
                     and self._fy is not None)

        # give audio time to start
        if has_audio:
            self._audio.wait_ready(timeout=3.0)

        wall0 = time.monotonic()
        n = 0
        first_frame = True

        try:
            while self._gen == gen and not self._evt.is_set():
                raw = _read_n(proc.stdout, fsz)
                if raw is None or self._gen != gen:
                    break

                frame_time = t0 + n * spf
                self._ct = frame_time

                if first_frame:
                    first_frame = False
                    wall0 = time.monotonic()

                # ── choose sync source for this frame ───
                a = self._audio
                use_audio = (has_audio and a.is_ready
                             and a.is_alive and not self._muted)

                if use_audio:
                    # wait until audio reaches this frame's time
                    for _ in range(1000):
                        if self._gen != gen or self._evt.is_set():
                            break
                        apos = a.media_position
                        if apos >= frame_time - 0.005:
                            break
                        wait = min((frame_time - apos) / speed, 0.05)
                        if wait > 0.001:
                            time.sleep(wait)
                        else:
                            break

                    if self._gen != gen or self._evt.is_set():
                        break

                    # skip if video fell too far behind audio
                    apos = a.media_position
                    if apos > frame_time + spf * 4:
                        n += 1
                        continue

                    # keep wall0 in sync for seamless fallback
                    wall0 = time.monotonic() - n * dspf
                else:
                    # wall-clock sync (no audio / muted)
                    target = wall0 + n * dspf
                    now = time.monotonic()
                    dt = target - now
                    if dt > 0.002:
                        time.sleep(dt)
                    elif dt < -0.1:
                        if dt < -dspf * 5:
                            wall0 = now - n * dspf
                        n += 1
                        continue

                # push frame to display queue
                try:
                    self._q.put_nowait(raw)
                except queue.Full:
                    try:
                        self._q.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self._q.put_nowait(raw)
                    except Exception:
                        pass

                n += 1
        except (OSError, ValueError):
            pass

        if self._gen == gen and not self._evt.is_set():
            self._playing = False
            self._root.after(0, self._on_eof)

    # ── hardware accel detection thread ────────────────
    def _detect_hw_thread(self, gen):
        if self._hwm == "off":
            if self._gen == gen:
                self._root.after(0, lambda: self._lhw.config(
                    text=self._S("stag"), fg="#aa6"))
            return

        cmd = [self._ff, "-v", "verbose"]
        if self._hwm == "auto":
            cmd += ["-hwaccel", "auto"]
        else:
            cmd += ["-hwaccel", self._hwm]
        cmd += ["-i", self._path,
                "-frames:v", "1", "-f", "null",
                "-an", "-sn", "-"]
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               timeout=15, **_pkw())
            txt = r.stderr.decode("utf-8", errors="ignore")
        except Exception:
            txt = ""

        if self._gen != gen:
            return

        hw_name = None
        for pat in [
            r"Using\s+auto\s+hwaccel\s+type\s+(\w+)",
            r"Using\s+(\w+)\s+hwaccel",
            r"hwaccel\s+type\s+(\w+)",
            r"HW\s+accel[:\s]+(\w+)",
            r"device\s+type[:\s]+(\w+)",
        ]:
            m = re.search(pat, txt, re.I)
            if m:
                val = m.group(1)
                if val.lower() not in ("auto", "type", "with", "new"):
                    hw_name = val
                    break
        if not hw_name:
            m = re.search(
                r"(\w+(?:_cuvid|_qsv|_nvdec|_amf|_vaapi|_vdpau"
                r"|_videotoolbox|_mediacodec|_d3d11va|_dxva2))",
                txt, re.I)
            if m:
                hw_name = m.group(1)
        if not hw_name:
            m = re.search(
                r"\b(d3d11va|dxva2|cuda|nvdec|cuvid|qsv|vaapi|vdpau"
                r"|videotoolbox|mediacodec|vulkan)\b",
                txt, re.I)
            if m:
                hw_name = m.group(1)
        if not hw_name and self._hwm not in ("auto", "off"):
            if self._hwm.lower() in txt.lower():
                hw_name = self._hwm

        if hw_name and self._gen == gen:
            self._hwd = hw_name
            self._root.after(0, lambda: self._lhw.config(
                text=self._S("htag").format(hw_name), fg="#6a6"))
        elif self._gen == gen:
            self._root.after(0, lambda: self._lhw.config(
                text=self._S("stag"), fg="#aa6"))

    def _on_eof(self):
        self._bpp.config(text="\u25B6")
        self._audio.stop()

    # ── display tick (main thread, ~66 Hz) ─────────────
    def _tick(self):
        if self._playing:
            latest = None
            try:
                while True:
                    latest = self._q.get_nowait()
            except queue.Empty:
                pass
            if latest is not None:
                try:
                    img = Image.frombytes("RGB", (self._dw, self._dh),
                                          latest)
                    self._frame = img
                    self._cv.show_img(img)
                except Exception:
                    pass
            self._bar.set_pos(self._ct)
            self._tv.set(
                f"{self._fmt(self._ct)} / "
                f"{self._fmt(self._info['duration'])}")
        else:
            try:
                while True:
                    self._q.get_nowait()
            except queue.Empty:
                pass
        self._root.after(15, self._tick)

    # ━━━━━━━━━━━━━━ Playback Controls ━━━━━━━━━━━━━━━━━
    def _toggle_play(self):
        if not self._path:
            return
        if self._playing:
            self._kill()
            self._paused = True
            self._bpp.config(text="\u25B6")
        elif self._paused:
            self._paused = False
            self._start(self._ct)
        else:
            self._start(0.0)

    def _do_stop(self):
        self._kill()
        self._paused = False
        self._ct = 0.0
        self._bar.set_pos(0)
        self._bpp.config(text="\u25B6")
        self._lhw.config(text="")
        if self._info:
            self._tv.set(f"00:00 / {self._fmt(self._info['duration'])}")
        else:
            self._tv.set("00:00 / 00:00")

    def _do_close(self):
        self._kill()
        self._paused = False
        self._ct = 0.0
        self._path = None
        self._info = None
        self._frame = None
        self._bar.dur = 0
        self._bar.set_pos(0)
        self._bpp.config(text="\u25B6")
        self._lhw.config(text="")
        self._tv.set("00:00 / 00:00")
        self._sub_mode = "off"
        self._sub_ext_path = None
        self._root.title(self._S("title"))
        self._show_hint()

    # ── drag: start / move / release ───────────────────
    def _on_drag_start(self):
        self._drag_was_playing = self._playing
        if self._playing:
            self._kill()
        self._bpp.config(text="\u25B6")

    def _on_drag_preview(self, t):
        if not self._path or not self._info:
            return
        self._ct = t
        self._bar.pos = t
        self._bar._draw()
        self._tv.set(
            f"{self._fmt(t)} / {self._fmt(self._info['duration'])}")
        self._drag_gen += 1
        dg = self._drag_gen
        if self._drag_busy:
            return
        self._drag_busy = True
        dw, dh, path, ff = self._dw, self._dh, self._path, self._ff

        def job():
            cmd = [ff, "-ss", f"{t:.3f}",
                   "-i", path,
                   "-vframes", "1", "-f", "rawvideo",
                   "-pix_fmt", "rgb24",
                   "-s", f"{dw}x{dh}",
                   "-v", "quiet", "pipe:1"]
            data = _run_bin(cmd, timeout=3)
            need = dw * dh * 3
            if len(data) >= need:
                img = Image.frombytes("RGB", (dw, dh), data[:need])
                self._frame = img
                self._root.after(0, lambda: self._cv.show_img(img))
            self._drag_busy = False
            if self._drag_gen != dg and self._bar._drag:
                newest_t = self._bar.pos
                self._root.after(
                    0, lambda: self._on_drag_preview(newest_t))

        threading.Thread(target=job, daemon=True).start()

    def _on_bar_release(self, t):
        was = self._drag_was_playing
        self._drag_was_playing = False
        self._ct = max(0.0, t)
        if was:
            self._start(self._ct)
        else:
            self._paused = True
            self._bar.set_pos(self._ct)
            if self._info:
                self._tv.set(
                    f"{self._fmt(self._ct)} / "
                    f"{self._fmt(self._info['duration'])}")
            self._grab_frame(self._ct)

    def _seek_to(self, t):
        if not self._path:
            return
        was = self._playing
        self._kill()
        self._ct = max(0.0, t)
        if was:
            self._start(self._ct)
        else:
            self._paused = True
            self._bar.set_pos(self._ct)
            if self._info:
                self._tv.set(
                    f"{self._fmt(self._ct)} / "
                    f"{self._fmt(self._info['duration'])}")
            self._grab_frame(self._ct)

    def _seek_rel(self, dt):
        if not self._info:
            return
        t = max(0.0, min(self._info["duration"], self._ct + dt))
        self._seek_to(t)

    def _grab_frame(self, t):
        dw, dh, path, ff = self._dw, self._dh, self._path, self._ff
        vf = self._build_vf_filter()

        def job():
            cmd = [ff, "-ss", f"{t:.3f}",
                   "-i", path,
                   "-vf", vf,
                   "-vframes", "1", "-f", "rawvideo",
                   "-pix_fmt", "rgb24",
                   "-v", "quiet", "pipe:1"]
            data = _run_bin(cmd, timeout=5)
            need = dw * dh * 3
            if len(data) >= need:
                img = Image.frombytes("RGB", (dw, dh), data[:need])
                self._frame = img
                self._root.after(0, lambda: self._cv.show_img(img))

        threading.Thread(target=job, daemon=True).start()

    def _next_frame(self):
        if not self._info:
            return
        if self._playing:
            self._kill()
            self._paused = True
            self._bpp.config(text="\u25B6")
        dt = 1.0 / self._info["fps"]
        self._ct = min(self._info["duration"], self._ct + dt)
        self._grab_frame(self._ct)
        self._bar.set_pos(self._ct)
        self._tv.set(
            f"{self._fmt(self._ct)} / "
            f"{self._fmt(self._info['duration'])}")

    def _set_speed(self, v):
        self._speed = v
        self._lsp.config(text=f"{v}x")
        if self._playing:
            t = self._ct
            self._kill()
            self._start(t)

    def _cycle_speed(self, d):
        try:
            idx = self.SPEEDS.index(self._speed)
        except ValueError:
            idx = self.SPEEDS.index(1.0)
        idx = max(0, min(len(self.SPEEDS) - 1, idx + d))
        self._set_speed(self.SPEEDS[idx])

    # ━━━━━━━━━━━━━━━━ Volume ━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _on_vol(self, val):
        self._vol = int(float(val))
        self._muted = False
        if hasattr(self, "_lvl") and self._lvl:
            self._lvl.config(text=f"{self._vol}%")
        if hasattr(self, "_bmu"):
            self._mu_icon()
        # debounce: restart audio 300 ms after last slider change
        if self._vol_timer is not None:
            self._root.after_cancel(self._vol_timer)
            self._vol_timer = None
        if (self._ui_ready and self._playing
                and self._info and self._info["has_audio"] and self._fy):
            self._vol_timer = self._root.after(
                300, self._restart_audio_vol)

    def _restart_audio_vol(self):
        self._vol_timer = None
        if (self._playing and self._info
                and self._info["has_audio"] and self._fy
                and not self._muted):
            self._audio.start(self._fy, self._path,
                              self._ct, self._vol, self._speed)

    def _chg_vol(self, d):
        self._vol = max(0, min(100, self._vol + d))
        self._vsc.set(self._vol)

    def _toggle_mute(self):
        self._muted = not self._muted
        self._mu_icon()
        if self._muted:
            self._audio.stop()
        elif (self._playing and self._info
              and self._info["has_audio"] and self._fy):
            self._audio.start(self._fy, self._path,
                              self._ct, self._vol, self._speed)

    def _mu_icon(self):
        if not hasattr(self, "_bmu"):
            return
        if self._muted or self._vol == 0:
            self._bmu.config(text="\U0001F507")
        elif self._vol < 50:
            self._bmu.config(text="\U0001F509")
        else:
            self._bmu.config(text="\U0001F50A")

    # ━━━━━━━━━━━━━━━ Fullscreen ━━━━━━━━━━━━━━━━━━━━━━━
    def _toggle_fs(self):
        self._fsc = not self._fsc
        self._root.attributes("-fullscreen", self._fsc)
        if self._fsc:
            self._ctrl.pack_forget()
            self._root.config(menu="")
        else:
            self._ctrl.pack(fill="x", side="bottom")
            self._root.config(menu=self._mb)

    # ━━━━━━━━━━━━━ Preview Tooltip ━━━━━━━━━━━━━━━━━━━━
    def _prev_hover(self, t, sx, sy):
        if not self._info or not self._path:
            return
        key = int(t * 2)
        ts = self._fmt(t)
        if key in self._pcache:
            self._tip.show(self._pcache[key], ts, sx, sy)
            return
        if self._pbusy:
            return
        self._pbusy = True
        path, ff = self._path, self._ff
        iw, ih = self._info["width"], self._info["height"]

        def job():
            pw = 160
            ph = max(2, int(pw * ih / max(1, iw)))
            ph += ph % 2
            cmd = [ff, "-ss", f"{t:.3f}",
                   "-i", path,
                   "-vframes", "1", "-f", "rawvideo",
                   "-pix_fmt", "rgb24",
                   "-s", f"{pw}x{ph}",
                   "-v", "quiet", "pipe:1"]
            try:
                data = _run_bin(cmd, timeout=3)
                need = pw * ph * 3
                if len(data) >= need:
                    img = Image.frombytes("RGB", (pw, ph), data[:need])
                    if len(self._pcache) > 200:
                        self._pcache.clear()
                    self._pcache[key] = img
                    self._root.after(
                        0, lambda: self._tip.show(img, ts, sx, sy))
            except Exception:
                pass
            finally:
                self._pbusy = False

        threading.Thread(target=job, daemon=True).start()

    def _prev_leave(self):
        self._tip.hide()

    def _check_tip_hide(self):
        try:
            mx = self._root.winfo_pointerx()
            my = self._root.winfo_pointery()
            bx = self._bar.winfo_rootx()
            by = self._bar.winfo_rooty()
            bw = self._bar.winfo_width()
            bh = self._bar.winfo_height()
            if not (bx <= mx <= bx + bw and by <= my <= by + bh):
                self._tip.hide()
        except Exception:
            pass
        self._root.after(300, self._check_tip_hide)

    # ━━━━━━━━━━━━━━ Settings Dialogs ━━━━━━━━━━━━━━━━━━
    def _set_boss(self):
        dlg = tk.Toplevel(self._root)
        dlg.title(self._S("boss"))
        dlg.geometry("340x110")
        dlg.transient(self._root)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text=self._S("bp").format(self._boss),
                 font=("Helvetica", 11), wraplength=310,
                 justify="center").pack(expand=True, padx=10, pady=10)

        def on_key(e):
            self._boss = e.keysym
            dlg.destroy()

        dlg.bind("<Key>", on_key)
        dlg.focus_force()

    def _set_hw(self, mode):
        self._hwm = mode
        if self._playing:
            t = self._ct
            self._kill()
            self._start(t)

    # ━━━━━━━━━━━━━━━━ Dialogs ━━━━━━━━━━━━━━━━━━━━━━━━━
    def _about(self):
        dlg = tk.Toplevel(self._root)
        dlg.title(self._S("about"))
        dlg.geometry("480x340")
        dlg.transient(self._root)
        dlg.resizable(False, False)

        ver_line = "unknown"
        try:
            ver_raw = _run_text([self._ff, "-version"], timeout=5)
            if ver_raw:
                ver_line = ver_raw.strip().split("\n")[0]
        except Exception:
            pass

        txt = self._S("abt")
        txt += f"\n\n{ver_line}"
        if self._fp:
            txt += f"\nffprobe: {self._fp}"
        if self._fy:
            txt += f"\nffplay: {self._fy}"
        else:
            txt += "\nffplay: (not found — no audio)"

        tk.Label(dlg, text=txt, font=("Helvetica", 10),
                 justify="center", wraplength=460).pack(
            expand=True, padx=10)
        tk.Button(dlg, text=self._S("ok"), width=10,
                  command=dlg.destroy).pack(pady=8)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    def _alert(self, msg):
        dlg = tk.Toplevel(self._root)
        dlg.title("!")
        dlg.geometry("420x140")
        dlg.transient(self._root)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text=msg, font=("Helvetica", 11),
                 wraplength=390, justify="center").pack(
            expand=True, padx=10)
        tk.Button(dlg, text=self._S("ok"), width=10,
                  command=dlg.destroy).pack(pady=8)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    # ━━━━━━━━━━━━━━━━━━ Quit ━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _quit(self):
        self._save_settings()
        self._kill()
        self._tip.destroy()
        try:
            self._root.destroy()
        except Exception:
            pass


# ━━━━━━━━━━━━━━━ Entry Point ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    app = Player()
    app._check_tip_hide()
    if len(sys.argv) > 1:
        p = sys.argv[1]
        if os.path.isfile(p):
            app._root.after(300, lambda: app._open_video(p))
    app.run()