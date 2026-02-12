#!/usr/bin/env python3
"""
StealthPlayer — privacy-focused FFmpeg video player (no history).
Required : Python 3.7+, Pillow (pip install Pillow)
Optional : tkinterdnd2        (pip install tkinterdnd2) for drag-and-drop
FFmpeg is searched in PATH first, then in ./lib/ beside this script.
"""

import tkinter as tk
from tkinter import ttk, filedialog
import subprocess, threading, time, os, sys, platform, json, queue, shutil, re
from pathlib import Path

try:
    from PIL import Image, ImageTk
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

# ━━━━━━━━━━━━━━━━━━━ i18n ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_L = {
    "en": {
        "title": "Player",
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
        "opa": "Opacity",
        "hw": "Hardware Decode",
        "hwa": "Auto",
        "hwd": "Disabled",
        "help": "Help",
        "about": "About",
        "abt": "StealthPlayer\nFFmpeg-based video player\nNo playback history is ever recorded.",
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
        "title": "播放器",
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
        "opa": "透明度",
        "hw": "硬件解码",
        "hwa": "自动",
        "hwd": "禁用",
        "help": "帮助",
        "about": "关于",
        "abt": "StealthPlayer\n基于 FFmpeg 的视频播放器\n不记录任何播放历史。",
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
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            **_pkw())
        return r.stdout.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _run_bin(cmd, timeout=5):
    try:
        r = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            **_pkw())
        return r.stdout
    except Exception:
        return b""


def _probe(ffprobe, path):
    txt = _run_text(
        [ffprobe, "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", path],
        timeout=15)
    if not txt:
        return None
    try:
        d = json.loads(txt)
    except json.JSONDecodeError:
        return None

    info = dict(duration=0.0, width=0, height=0, fps=30.0,
                has_audio=False, vcodec="")
    info["duration"] = float(d.get("format", {}).get("duration", 0))
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

    def __init__(self):
        self._ff = _find("ffmpeg")
        self._fp = _find("ffprobe")
        self._fy = _find("ffplay")

        self._lang = "en"
        self._path = None
        self._info = None
        self._playing = False
        self._paused = False
        self._ct = 0.0
        self._vol = 100
        self._muted = False
        self._speed = 1.0
        self._boss = "Escape"
        self._hwm = "auto"
        self._hwd = ""
        self._fsc = False
        self._gen = 0
        self._evt = threading.Event()
        self._q = queue.Queue(maxsize=8)
        self._vp = None
        self._ap = None
        self._frame = None
        self._dw = 0
        self._dh = 0
        self._pcache = {}
        self._pbusy = False
        self._ui_ready = False
        self._click_pending = None
        self._drag_gen = 0
        self._drag_busy = False

        self._root = TkinterDnD.Tk() if _DND else tk.Tk()
        self._root.title("Player")
        self._root.geometry("960x600")
        self._root.minsize(480, 320)
        self._root.configure(bg="black")

        if not self._ff:
            self._root.withdraw()
            from tkinter import messagebox
            messagebox.showerror("Error", _L[self._lang]["noff"])
            sys.exit(1)

        self._build_ui()
        self._ui_ready = True
        self._build_menus()
        self._bind_keys()

        if _DND:
            self._root.drop_target_register(DND_FILES)
            self._root.dnd_bind("<<Drop>>", self._on_drop)

        self._root.after(250, self._show_hint)
        self._tick()

    def run(self):
        self._root.mainloop()

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

    # ━━━━━━━━━━━━━━━━━ Build UI ━━━━━━━━━━━━━━━━━━━━━━━
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

        self._mb.add_cascade(label="File", menu=self._mf)
        self._mb.add_cascade(label="Playback", menu=self._mp)
        self._mb.add_cascade(label="Audio", menu=self._ma)
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
        self._bar.on_seek = self._seek_to
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
        self._mb.entryconfigure(4, label=S("settings"))
        self._mb.entryconfigure(5, label=S("help"))

        for m in (self._mf, self._mp, self._ma, self._ms,
                  self._mh, self._msp, self._ml, self._mhw,
                  self._mop):
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

        self._ml.add_command(label="English",
                             command=lambda: self._set_lang("en"))
        self._ml.add_command(label="\u4E2D\u6587",
                             command=lambda: self._set_lang("zh"))
        self._ms.add_cascade(label=S("lang"), menu=self._ml)

        self._ms.add_command(label=S("boss"), command=self._set_boss)

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
                command=lambda v=p: self._root.attributes("-alpha", v / 100))
        self._ms.add_cascade(label=S("opa"), menu=self._mop)

        self._mh.add_command(label=S("about"), command=self._about)

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
        self._bind_boss()
        r.protocol("WM_DELETE_WINDOW", self._quit)

    def _bind_boss(self):
        try:
            self._root.unbind_all(f"<{self._boss}>")
        except Exception:
            pass
        self._root.bind(f"<{self._boss}>", lambda e: self._quit())

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

        w, h = info["width"], info["height"]
        if h > 1080:
            w = int(w * 1080 / h)
            h = 1080
        self._dw = w + (w % 2)
        self._dh = h + (h % 2)

        self._root.title(
            f"{os.path.basename(path)} — {self._S('title')}")
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

        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

        cmd = [self._ff]
        if self._hwm == "auto":
            cmd += ["-hwaccel", "auto"]
        elif self._hwm != "off":
            cmd += ["-hwaccel", self._hwm]
        if t > 0.5:
            cmd += ["-ss", f"{t:.3f}"]
        cmd += ["-i", self._path,
                "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", f"{self._dw}x{self._dh}",
                "-an", "-sn",
                "-v", "info", "pipe:1"]
        try:
            self._vp = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=self._dw * self._dh * 3 * 2,
                **_pkw())
        except Exception as exc:
            self._alert(str(exc))
            self._playing = False
            return

        if self._info["has_audio"] and self._fy and not self._muted:
            self._start_audio(t)

        threading.Thread(target=self._vloop, args=(gen,),
                         daemon=True).start()
        threading.Thread(target=self._sloop, args=(gen,),
                         daemon=True).start()

        self._bpp.config(text="\u23F8")

    def _start_audio(self, t):
        self._stop_audio()
        cmd = [self._fy, "-nodisp", "-autoexit", "-loglevel", "quiet"]
        if t > 0.5:
            cmd += ["-ss", f"{t:.3f}"]
        cmd += ["-volume", str(self._vol)]
        if abs(self._speed - 1.0) > 0.01:
            parts = []
            v = self._speed
            while v > 2.0:
                parts.append("atempo=2.0")
                v /= 2.0
            while v < 0.5:
                parts.append("atempo=0.5")
                v /= 0.5
            parts.append(f"atempo={v:.4f}")
            cmd += ["-af", ",".join(parts)]
        cmd += ["-i", self._path]
        try:
            self._ap = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **_pkw())
        except Exception:
            self._ap = None

    def _stop_audio(self):
        if self._ap:
            try:
                self._ap.terminate()
            except Exception:
                pass
            try:
                self._ap.wait(timeout=2)
            except Exception:
                try:
                    self._ap.kill()
                except Exception:
                    pass
            self._ap = None

    def _kill(self):
        self._evt.set()
        self._playing = False
        self._stop_audio()
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
            try:
                p.stderr.close()
            except Exception:
                pass
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    # ── video reader thread ────────────────────────────
    def _vloop(self, gen):
        proc = self._vp
        if not proc:
            return
        fsz = self._dw * self._dh * 3
        fps = self._info["fps"]
        spf = 1.0 / fps
        dspf = spf / max(0.1, self._speed)
        t0 = self._ct
        w0 = time.monotonic()
        n = 0
        try:
            while self._gen == gen and not self._evt.is_set():
                raw = _read_n(proc.stdout, fsz)
                if raw is None or self._gen != gen:
                    break
                n += 1
                self._ct = t0 + n * spf

                tgt = w0 + n * dspf
                dt = tgt - time.monotonic()
                if dt > 0.002:
                    time.sleep(dt)
                elif dt < -dspf * 10:
                    w0 = time.monotonic() - n * dspf

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
        except (OSError, ValueError):
            pass
        if self._gen == gen and not self._evt.is_set():
            self._playing = False
            self._root.after(0, self._on_eof)

    # ── stderr reader thread (detect hw accel name) ────
    def _sloop(self, gen):
        proc = self._vp
        if not proc or not proc.stderr:
            return
        found_hw = False
        all_text = []
        try:
            while self._gen == gen and not self._evt.is_set():
                raw_line = proc.stderr.readline()
                if not raw_line:
                    break
                txt = raw_line.decode("utf-8", errors="ignore")
                all_text.append(txt)
                if found_hw:
                    continue
                # Try to detect the specific hwaccel decoder being used
                # e.g. "decoder: h264_cuvid" or "Using auto hwaccel type d3d11va"
                for pat in [
                    r"decoder\s*[:\s]\s*(\w+_cuvid|\w+_qsv|\w+_nvdec|\w+_amf|\w+_vaapi|\w+_vdpau|\w+_videotoolbox|\w+_mediacodec|\w+_mf|\w+_d3d11va|\w+_dxva2)",
                    r"using\s+(\w+)\s+hwaccel",
                    r"hwaccel\s+type\s+(\w+)",
                    r"device\s+type\s+(\w+)",
                    r"Using\s+hwaccel\s+(\w+)",
                    r"HW\s+accel[:\s]+(\w+)",
                    r"hw[/_]?accel[:\s]+(\w+)",
                ]:
                    m = re.search(pat, txt, re.I)
                    if m:
                        self._hwd = m.group(1)
                        found_hw = True
                        self._root.after(0, self._upd_hw)
                        break
        except Exception:
            pass
        # If no pattern matched yet, do a second pass on accumulated text
        if self._gen == gen and not found_hw:
            full = "".join(all_text)
            # Look for hwaccel type mentions in full output
            for pat in [
                r"using\s+(\w+)\s+hwaccel",
                r"hwaccel\s+type\s+(\w+)",
                r"device\s+type[:\s]+(\w+)",
                r"HW\s+decoder[:\s]+(\w+)",
                r"(d3d11va|dxva2|cuda|nvdec|cuvid|qsv|vaapi|vdpau|videotoolbox|mediacodec|vulkan|opencl)",
            ]:
                m = re.search(pat, full, re.I)
                if m:
                    self._hwd = m.group(1)
                    found_hw = True
                    self._root.after(0, self._upd_hw)
                    break
        if self._gen == gen and not found_hw:
            self._root.after(0, self._upd_hw_sw)

    def _on_eof(self):
        self._bpp.config(text="\u25B6")
        self._stop_audio()

    # ── display tick (main thread, ~66 Hz) ─────────────
    def _tick(self):
        latest = None
        try:
            while True:
                latest = self._q.get_nowait()
        except queue.Empty:
            pass
        if latest is not None:
            try:
                img = Image.frombytes("RGB", (self._dw, self._dh), latest)
                self._frame = img
                self._cv.show_img(img)
            except Exception:
                pass
        if self._playing and self._info:
            self._bar.set_pos(self._ct)
            self._tv.set(
                f"{self._fmt(self._ct)} / "
                f"{self._fmt(self._info['duration'])}")
        self._root.after(15, self._tick)

    def _upd_hw(self):
        if self._hwd:
            self._lhw.config(
                text=self._S("htag").format(self._hwd), fg="#6a6")

    def _upd_hw_sw(self):
        if self._playing and not self._hwd:
            self._lhw.config(text=self._S("stag"), fg="#aa6")

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
        self._root.title(self._S("title"))
        self._show_hint()

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

    # ── drag preview: show frame at dragged position in real time ──
    def _on_drag_preview(self, t):
        """Called continuously while user drags the progress bar."""
        if not self._path or not self._info:
            return
        self._ct = t
        self._bar.set_pos(t)
        self._tv.set(
            f"{self._fmt(t)} / {self._fmt(self._info['duration'])}")
        # Throttled frame grab — skip if a previous one is still running
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
            if len(data) >= need and self._drag_gen == dg:
                img = Image.frombytes("RGB", (dw, dh), data[:need])
                self._frame = img
                self._root.after(0, lambda: self._cv.show_img(img))
            self._drag_busy = False
            # If user moved further while we were busy, fire one more
            if self._drag_gen != dg and self._bar._drag:
                self._root.after(0, lambda: self._on_drag_preview(self._bar.pos))

        threading.Thread(target=job, daemon=True).start()

    def _grab_frame(self, t):
        dw, dh, path, ff = self._dw, self._dh, self._path, self._ff

        def job():
            cmd = [ff, "-ss", f"{t:.3f}",
                   "-i", path,
                   "-vframes", "1", "-f", "rawvideo",
                   "-pix_fmt", "rgb24",
                   "-s", f"{dw}x{dh}",
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
        if self._ui_ready and self._playing and self._info and self._info["has_audio"]:
            self._start_audio(self._ct)

    def _chg_vol(self, d):
        self._vol = max(0, min(100, self._vol + d))
        self._vsc.set(self._vol)

    def _toggle_mute(self):
        self._muted = not self._muted
        self._mu_icon()
        if self._muted:
            self._stop_audio()
        elif self._playing and self._info and self._info["has_audio"]:
            self._start_audio(self._ct)

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

    # ━━━━━━━━━━━━━━ Global tooltip cleanup ━━━━━━━━━━━━
    def _check_tip_hide(self):
        """Periodically check if mouse is still over the progress bar; hide tooltip if not."""
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
            old = self._boss
            self._boss = e.keysym
            try:
                self._root.unbind(f"<{old}>")
            except Exception:
                pass
            self._bind_boss()
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
        dlg.geometry("400x220")
        dlg.transient(self._root)
        dlg.resizable(False, False)

        txt = self._S("abt")
        txt += f"\n\nFFmpeg: {self._ff}"
        if self._fp:
            txt += f"\nffprobe: {self._fp}"
        if self._fy:
            txt += f"\nffplay: {self._fy}"
        else:
            txt += "\nffplay: (not found — no audio)"

        tk.Label(dlg, text=txt, font=("Helvetica", 10),
                 justify="center", wraplength=380).pack(
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