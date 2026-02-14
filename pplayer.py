#!/usr/bin/env python3
"""
PPlayer — privacy-focused FFmpeg video player (no history).
Refactored with PyQt6 for high performance.
Required : Python 3.7+, Pillow, PyQt6
FFmpeg is searched in PATH first, then in ./lib/ beside this script.
"""

import sys
import os
import time
import json
import shutil
import subprocess
import threading
import queue
import re
import platform
import tempfile
import uuid
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow is required: pip install Pillow")
    sys.exit(1)

try:
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, 
                                 QVBoxLayout, QHBoxLayout, QFileDialog, QMenu, 
                                 QSlider, QPushButton, QFrame, QDialog, QLineEdit,
                                 QToolTip, QSizePolicy)
    from PyQt6.QtCore import (Qt, QTimer, pyqtSignal, QObject, QEvent, QPoint, 
                              QSize, QRect)
    from PyQt6.QtGui import (QImage, QPixmap, QPainter, QColor, QAction, 
                             QKeySequence, QIcon, QFont, QCursor, QScreen)
except ImportError:
    print("PyQt6 is required: pip install PyQt6")
    sys.exit(1)

_W = platform.system() == "Windows"

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
            "FFmpeg-based video player (PyQt6)\n"
            "No playback history is ever recorded.\n\n"
            "This software uses FFmpeg.\n"
            "https://ffmpeg.org"
        ),
        "hint": "Drop a video file here\nor use File → Open",
        "htag": "HW: {}",
        "stag": "SW Decode",
        "noff": "FFmpeg not found!\nInstall FFmpeg or place binaries in ./lib/",
        "ep": "Enter file path or URL:",
        "bp": "Press a key to set as new boss key.\nCurrent: {}",
        "eo": "Cannot open:\n{}",
        "ok": "OK",
        "cancel": "Cancel",
        "sub_extracting": "Loading subtitles (RAM)...",
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
            "基于 FFmpeg 的视频播放器 (PyQt6)\n"
            "不记录任何播放历史。\n\n"
            "本软件使用 FFmpeg。\n"
            "https://ffmpeg.org"
        ),
        "hint": "拖放视频文件到此处\n或使用 文件→打开",
        "htag": "硬解: {}",
        "stag": "软件解码",
        "noff": "未找到 FFmpeg！\n请安装 FFmpeg 或将其放入 ./lib/ 目录",
        "ep": "输入文件路径或 URL：",
        "bp": "按下一个键设为新的老板键\n当前：{}",
        "eo": "无法打开：\n{}",
        "ok": "确定",
        "cancel": "取消",
        "sub_extracting": "正在加载字幕 (内存)...",
    },
}

# ━━━━━━━━━━━━━━━ FFmpeg helpers ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _find(name):
    if getattr(sys, 'frozen', False):
        base_path = Path(sys.executable).parent
    else:
        base_path = Path(os.path.dirname(os.path.abspath(__file__)))

    lib_dir = base_path / "lib"
    target_exe = f"{name}.exe" if _W else name
    local_path = lib_dir / target_exe
    
    if local_path.is_file():
        return str(local_path)

    system_path = shutil.which(name)
    if system_path:
        return system_path
        
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
    def __init__(self):
        self._proc = None
        self._proc_src = None
        self._pos = 0.0
        self._pos_wall = 0.0
        self._seek_time = 0.0
        self._speed = 1.0
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._alive = False

    def start(self, ffplay_path, ffmpeg_path, file_path, seek_time, volume, speed):
        self.stop()
        self._speed = max(0.1, speed)
        self._seek_time = seek_time
        with self._lock:
            self._pos = seek_time
            self._pos_wall = time.monotonic()
        self._ready.clear()
        self._alive = True

        cmd_src = [ffmpeg_path, "-ss", f"{seek_time:.3f}", "-i", file_path,
                   "-vn", "-f", "wav", "-"]
        
        cmd_play = [ffplay_path, "-nodisp", "-autoexit", "-vn",
                    "-loglevel", "info"]
        cmd_play += ["-volume", str(volume)]
        
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
            cmd_play += ["-af", ",".join(parts)]
        
        cmd_play += ["-i", "-"]

        try:
            self._proc_src = subprocess.Popen(
                cmd_src, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                **_pkw())
            self._proc = subprocess.Popen(
                cmd_play, stdin=self._proc_src.stdout,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                **_pkw())
            self._proc_src.stdout.close()
        except Exception:
            self._alive = False
            return
        threading.Thread(target=self._reader, daemon=True).start()

    def stop(self):
        self._alive = False
        self._ready.clear()
        
        p = self._proc
        self._proc = None
        if p:
            try: p.terminate()
            except: pass
            try: p.wait(timeout=0.5)
            except: 
                try: p.kill()
                except: pass
        
        p = self._proc_src
        self._proc_src = None
        if p:
            try: p.terminate()
            except: pass
            try: p.wait(timeout=0.5)
            except:
                try: p.kill()
                except: pass

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
        with self._lock:
            if not self._ready.is_set():
                return self._seek_time
            elapsed = time.monotonic() - self._pos_wall
            interp = self._pos + elapsed
            if abs(self._speed - 1.0) < 0.01:
                return interp
            return self._seek_time + (interp - self._seek_time) * self._speed

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
                raw_pos = float(m.group(1))
                pos = raw_pos + self._seek_time
                with self._lock:
                    self._pos = pos
                    self._pos_wall = time.monotonic()
                if not self._ready.is_set():
                    self._ready.set()
            except ValueError:
                pass

# ━━━━━━━━━━━━━━━ Custom Widgets (PyQt6) ━━━━━━━━━━━━━━━━━━━

class VideoWidget(QWidget):
    doubleClicked = pyqtSignal()
    clicked = pyqtSignal()
    wheelScrolled = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setStyleSheet("background-color: black;")
        self._image = None
        self._text = ""
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._emit_click)

    def set_image(self, qimg):
        self._image = qimg
        self._text = ""
        self.update()

    def set_text(self, text):
        self._image = None
        self._text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        if self._image:
            # Scale and center
            target_rect = self.rect()
            # Use SmoothTransformation for high quality scaling (removes aliasing)
            scaled_img = self._image.scaled(target_rect.size(), 
                                          Qt.AspectRatioMode.KeepAspectRatio, 
                                          Qt.TransformationMode.SmoothTransformation)
            
            x = (target_rect.width() - scaled_img.width()) // 2
            y = (target_rect.height() - scaled_img.height()) // 2
            painter.drawImage(x, y, scaled_img)
        
        elif self._text:
            painter.setPen(QColor("#555555"))
            font = painter.font()
            font.setPointSize(16)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_timer.start(300)
        elif event.button() == Qt.MouseButton.BackButton:
            self.wheelScrolled.emit(5) # Map extra buttons
        elif event.button() == Qt.MouseButton.ForwardButton:
            self.wheelScrolled.emit(-5)

    def mouseDoubleClickEvent(self, event):
        self._click_timer.stop()
        self.doubleClicked.emit()

    def _emit_click(self):
        self.clicked.emit()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.wheelScrolled.emit(5)
        else:
            self.wheelScrolled.emit(-5)

class SeekSlider(QWidget):
    seekRequested = pyqtSignal(float)
    dragStarted = pyqtSignal()
    dragPosition = pyqtSignal(float)
    hoverMove = pyqtSignal(float, int, int)
    hoverLeave = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self.setMouseTracking(True)
        self.duration = 0.0
        self.position = 0.0
        self._dragging = False

    def set_pos(self, t):
        if not self._dragging:
            self.position = t
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        cy = h // 2
        
        # Background
        painter.fillRect(4, cy - 3, w - 8, 6, QColor("#444444"))
        
        if self.duration > 0:
            ratio = self.position / self.duration
            px = int(4 + (w - 8) * ratio)
            px = max(4, min(w - 4, px))
            
            # Fill
            painter.fillRect(4, cy - 3, px - 4, 6, QColor("#0078d4"))
            
            # Handle
            painter.setBrush(Qt.GlobalColor.white)
            painter.setPen(QColor("#0078d4"))
            painter.drawEllipse(QPoint(px, cy), 6, 6)

    def _time_at_x(self, x):
        w = self.width()
        if self.duration <= 0 or w <= 8:
            return 0.0
        ratio = (x - 4) / (w - 8)
        return max(0.0, min(self.duration, ratio * self.duration))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.position = self._time_at_x(event.pos().x())
            self.update()
            self.dragStarted.emit()
            self.hoverLeave.emit()
            self.dragPosition.emit(self.position)

    def mouseMoveEvent(self, event):
        t = self._time_at_x(event.pos().x())
        if self._dragging:
            self.position = t
            self.update()
            self.dragPosition.emit(self.position)
        else:
            if self.duration > 0:
                self.hoverMove.emit(t, event.globalPosition().x(), event.globalPosition().y())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.position = self._time_at_x(event.pos().x())
            self.update()
            self.seekRequested.emit(self.position)

    def leaveEvent(self, event):
        self.hoverLeave.emit()

class PreviewTip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.img_label = QLabel()
        self.img_label.setStyleSheet("border: 1px solid #444; background: black;")
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.txt_label = QLabel()
        self.txt_label.setStyleSheet("background: black; color: white; padding: 2px;")
        self.txt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.txt_label.setFont(QFont("Helvetica", 9))
        
        layout.addWidget(self.img_label)
        layout.addWidget(self.txt_label)

    def show_tip(self, qimg, text, gx, gy):
        pix = QPixmap.fromImage(qimg)
        self.img_label.setPixmap(pix)
        self.txt_label.setText(text)
        
        # Calculate position
        w, h = pix.width(), pix.height() + 20
        nx = gx - w // 2
        ny = gy - h - 40
        
        # Screen boundary check
        screen = QApplication.screenAt(QPoint(gx, gy))
        if screen:
            geo = screen.geometry()
            if nx < geo.left(): nx = geo.left() + 5
            if nx + w > geo.right(): nx = geo.right() - w - 5
            if ny < geo.top(): ny = gy + 20 # Show below if not enough space above
        
        self.move(nx, ny)
        self.show()

# ━━━━━━━━━━━━━━━━━━ Player ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Player(QMainWindow):
    frameReady = pyqtSignal(bytes, int, int) # Signal to update UI from thread
    hwInfoReady = pyqtSignal(str, str)
    previewReady = pyqtSignal(int, object) # key, QImage

    SPEEDS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]

    def __init__(self):
        super().__init__()
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
        self._vp = None
        self._audio = _AudioPlayer()
        self._dw = 0
        self._dh = 0
        self._pcache = {}
        self._pbusy = False
        self._drag_gen = 0
        self._drag_busy = False
        self._drag_was_playing = False
        self._vol_timer = None
        self._hwd = ""
        self._sync_t0 = 0.0
        
        self._render_w = 0
        self._render_h = 0

        self._sub_mode = "off"
        self._sub_ext_path = None
        self._sub_data = None
        self._sub_pipe_name = None
        self._sub_thread = None
        self._sub_stop_evt = threading.Event()

        if not self._ff:
            print(_L[self._lang]["noff"])
            sys.exit(1)

        self.setWindowTitle("PPlayer")
        self.resize(800, 500)
        if self._saved_geo:
            try:
                w, h = map(int, self._saved_geo.split("x"))
                self.resize(w, h)
            except: pass
            
        self.setMinimumSize(480, 320)
        self.setWindowOpacity(self._opacity)
        self.setAcceptDrops(True)

        self._build_ui()
        self._build_menus()
        
        # Signals
        self.frameReady.connect(self._on_frame_ready)
        self.hwInfoReady.connect(self._on_hw_info)
        self.previewReady.connect(self._on_preview_ready)

        self._vsc.setValue(self._vol)
        self._lsp.setText(f"{self._speed}x")
        self._mu_icon()

        QTimer.singleShot(250, self._show_hint)
        
        # Tick timer for UI updates (progress bar)
        self._tick_timer = QTimer()
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(50)

    def _S(self, k):
        return _L.get(self._lang, _L["en"]).get(k, k)

    @staticmethod
    def _fmt(s):
        s = max(0, int(s))
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"

    def _show_hint(self):
        self._cv.set_text(self._S("hint"))

    def _load_settings(self):
        defaults = dict(lang="en", volume=100, speed=1.0,
                        hw_mode="auto", boss_key="Escape",
                        boss_any=False, opacity=1.0,
                        geometry="800x500")
        try:
            if _CFG_FILE.exists():
                with open(_CFG_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                for k in defaults:
                    if k in d:
                        defaults[k] = d[k]
        except Exception:
            pass
        if defaults["lang"] not in _L:
            defaults["lang"] = "en"
        defaults["volume"] = max(0, min(100, int(defaults["volume"])))
        if defaults["speed"] not in Player.SPEEDS:
            defaults["speed"] = 1.0
        defaults["opacity"] = max(0.3, min(1.0, float(defaults["opacity"])))
        return defaults

    def _save_settings(self):
        try:
            _CFG_DIR.mkdir(parents=True, exist_ok=True)
            geo = f"{self.width()}x{self.height()}"
            d = dict(lang=self._lang, volume=self._vol,
                     speed=self._speed, hw_mode=self._hwm,
                     boss_key=self._boss, boss_any=self._boss_any,
                     opacity=self._opacity, geometry=geo)
            with open(_CFG_FILE, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._cv = VideoWidget()
        self._cv.clicked.connect(self._toggle_play)
        self._cv.doubleClicked.connect(self._toggle_fs)
        self._cv.wheelScrolled.connect(self._chg_vol)
        main_layout.addWidget(self._cv, 1)

        # Controls
        self._ctrl = QFrame()
        self._ctrl.setStyleSheet("background-color: #181818;")
        self._ctrl.setFixedHeight(64)
        ctrl_layout = QVBoxLayout(self._ctrl)
        ctrl_layout.setContentsMargins(4, 4, 4, 4)
        ctrl_layout.setSpacing(2)

        self._bar = SeekSlider()
        self._bar.seekRequested.connect(self._on_bar_release)
        self._bar.dragStarted.connect(self._on_drag_start)
        self._bar.dragPosition.connect(self._on_drag_preview)
        self._bar.hoverMove.connect(self._prev_hover)
        self._bar.hoverLeave.connect(self._prev_leave)
        ctrl_layout.addWidget(self._bar)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        # Button Style
        B_STYLE = """
            QPushButton {
                background-color: #181818; color: white; border: none;
                font-family: "Segoe UI Symbol"; font-size: 16px; padding: 4px;
            }
            QPushButton:hover { background-color: #333; }
        """

        self._bpp = QPushButton("\u25B6")
        self._bpp.setStyleSheet(B_STYLE)
        self._bpp.clicked.connect(self._toggle_play)
        btn_layout.addWidget(self._bpp)

        b_stop = QPushButton("\u23F9")
        b_stop.setStyleSheet(B_STYLE)
        b_stop.clicked.connect(self._do_stop)
        btn_layout.addWidget(b_stop)

        self._tv = QLabel("00:00 / 00:00")
        self._tv.setStyleSheet("color: #aaa; font-family: Consolas; font-size: 12px;")
        btn_layout.addWidget(self._tv)
        
        btn_layout.addStretch()

        self._lhw = QLabel("")
        self._lhw.setStyleSheet("color: #6a6; font-size: 11px;")
        btn_layout.addWidget(self._lhw)

        self._lsp = QLabel("1.0x")
        self._lsp.setStyleSheet("color: #aaa; font-size: 11px;")
        btn_layout.addWidget(self._lsp)

        self._bmu = QPushButton("\U0001F50A")
        self._bmu.setStyleSheet(B_STYLE)
        self._bmu.clicked.connect(self._toggle_mute)
        btn_layout.addWidget(self._bmu)

        self._vsc = QSlider(Qt.Orientation.Horizontal)
        self._vsc.setRange(0, 100)
        self._vsc.setFixedWidth(80)
        self._vsc.valueChanged.connect(self._on_vol)
        btn_layout.addWidget(self._vsc)

        self._lvl = QLabel("100%")
        self._lvl.setStyleSheet("color: #aaa; font-size: 11px;")
        self._lvl.setFixedWidth(35)
        btn_layout.addWidget(self._lvl)

        self._bfs = QPushButton("⛶")
        self._bfs.setStyleSheet(B_STYLE)
        self._bfs.clicked.connect(self._toggle_fs)
        btn_layout.addWidget(self._bfs)

        ctrl_layout.addLayout(btn_layout)
        main_layout.addWidget(self._ctrl)

        self._tip = PreviewTip(self)

    def _add_action(self, menu, text, slot, shortcut=None):
        """Helper to add action safely in PyQt6"""
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        menu.addAction(action)
        return action

    def _build_menus(self):
        mb = self.menuBar()
        mb.clear()
        S = self._S

        mf = mb.addMenu(S("file"))
        self._add_action(mf, S("open"), self._open_file, "Ctrl+O")
        self._add_action(mf, S("open_path"), self._open_path, "Ctrl+L")
        mf.addSeparator()
        self._add_action(mf, S("close"), self._do_close)
        mf.addSeparator()
        self._add_action(mf, S("exit"), self.close)

        mp = mb.addMenu(S("playback"))
        self._add_action(mp, S("pp"), self._toggle_play, "Space")
        self._add_action(mp, S("stop"), self._do_stop)
        mp.addSeparator()
        self._add_action(mp, S("bwd5"), lambda: self._seek_rel(-5), "Left")
        self._add_action(mp, S("fwd5"), lambda: self._seek_rel(5), "Right")
        self._add_action(mp, S("bwd30"), lambda: self._seek_rel(-30), "Ctrl+Left")
        self._add_action(mp, S("fwd30"), lambda: self._seek_rel(30), "Ctrl+Right")
        self._add_action(mp, S("nf"), self._next_frame, ".")
        mp.addSeparator()
        
        msp = mp.addMenu(S("spd"))
        for s in self.SPEEDS:
            self._add_action(msp, f"{s}x", lambda v=s: self._set_speed(v))
            
        mp.addSeparator()
        self._add_action(mp, S("fs"), self._toggle_fs, "F")

        ma = mb.addMenu(S("audio"))
        self._add_action(ma, S("vu"), lambda: self._chg_vol(5), "Up")
        self._add_action(ma, S("vd"), lambda: self._chg_vol(-5), "Down")
        self._add_action(ma, S("mute"), self._toggle_mute, "M")

        msub = mb.addMenu(S("sub"))
        self._add_action(msub, S("sub_off"), self._sub_off)
        msub.addSeparator()
        if self._info and self._info.get("subs"):
            for sub in self._info["subs"]:
                si = sub["stream_idx"]
                codec = sub.get("codec", "")
                # Capture variables in lambda
                self._add_action(msub, sub["label"], lambda idx=si, c=codec: self._sub_embed(idx, c))
            msub.addSeparator()
        self._add_action(msub, S("sub_ext"), self._sub_load_ext)

        ms = mb.addMenu(S("settings"))
        ml = ms.addMenu(S("lang"))
        self._add_action(ml, "English", lambda: self._set_lang("en"))
        self._add_action(ml, "\u4E2D\u6587", lambda: self._set_lang("zh"))

        self._add_action(ms, S("boss"), self._set_boss)
        
        act_boss_any = QAction(S("boss_any"), self, checkable=True)
        act_boss_any.setChecked(self._boss_any)
        act_boss_any.triggered.connect(self._toggle_boss_any)
        ms.addAction(act_boss_any)

        mhw = ms.addMenu(S("hw"))
        self._add_action(mhw, S("hwa"), lambda: self._set_hw("auto"))
        self._add_action(mhw, S("hwd"), lambda: self._set_hw("off"))
        for a in _hwaccels(self._ff):
            self._add_action(mhw, a, lambda v=a: self._set_hw(v))

        mop = ms.addMenu(S("opa"))
        for p in (100, 90, 80, 70, 60, 50, 40, 30):
            self._add_action(mop, f"{p}%", lambda v=p: self._set_opacity(v))

        mh = mb.addMenu(S("help"))
        self._add_action(mh, S("about"), self._about)

    def keyPressEvent(self, event):
        key = event.key()
        # Boss key check
        try:
            ks = QKeySequence(key).toString()
            if ks.lower() == self._boss.lower() or (self._boss == "Escape" and key == Qt.Key.Key_Escape):
                self.close()
                return
        except: pass

        if self._boss_any:
            # Simple check for non-modifier keys
            if key not in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
                if not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
                    self.close()
                    return

        # Shortcuts that might not be in menus or need global handling
        if key == Qt.Key.Key_F11:
            self._toggle_fs()
        elif key == Qt.Key.Key_BracketRight:
            self._cycle_speed(1)
        elif key == Qt.Key.Key_BracketLeft:
            self._cycle_speed(-1)
        
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self._open_video(files[0])

    def _toggle_boss_any(self, checked):
        self._boss_any = checked

    def _set_lang(self, c):
        self._lang = c
        self._apply_lang()
        if not self._playing and not self._path:
            self._show_hint()

    def _apply_lang(self):
        self.setWindowTitle(
            f"{os.path.basename(self._path)} — {self._S('title')}"
            if self._path else self._S("title"))
        self._build_menus()

    def _open_file(self):
        ft = "Video (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.ts *.mpg *.mpeg *.3gp *.ogv *.rmvb *.rm *.vob);;All (*.*)"
        p, _ = QFileDialog.getOpenFileName(self, self._S("open"), "", ft)
        if p:
            self._open_video(p)

    def _open_path(self):
        text, ok = QInputDialog_getText(self, self._S("open_path"), self._S("ep"))
        if ok and text:
            self._open_video(text.strip())

    # ━━━━━━━━━━━━━ Subtitle Logic ━━━━━━━━━━━━━
    def _sub_off(self):
        changed = self._sub_mode != "off"
        self._sub_mode = "off"
        self._sub_ext_path = None
        self._cleanup_sub_pipe()
        if changed and self._playing:
            t = self._ct
            self._kill()
            self._start(t)

    def _cleanup_sub_pipe(self):
        self._sub_stop_evt.set()
        if self._sub_thread and self._sub_thread.is_alive():
            self._sub_thread.join(timeout=0.2)
        self._sub_thread = None
        
        if self._sub_pipe_name:
            if not _W:
                try: os.unlink(self._sub_pipe_name)
                except: pass
        self._sub_pipe_name = None
        self._sub_data = None

    def _extract_subtitle_to_mem(self, stream_idx, codec):
        ext = "srt"
        if "ass" in codec or "ssa" in codec: ext = "ass"
        elif "vtt" in codec: ext = "vtt"
        
        self._cv.set_text(self._S("sub_extracting"))
        QApplication.processEvents()

        cmd = [self._ff, "-y", "-i", self._path, "-map", f"0:s:{stream_idx}"]
        cmd += ["-f", ext, "-"]
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, **_pkw())
            return r.stdout
        except Exception:
            return None

    def _serve_pipe_windows(self, pipe_name, data):
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        INVALID_HANDLE_VALUE = -1
        while not self._sub_stop_evt.is_set():
            h_pipe = kernel32.CreateNamedPipeW(
                pipe_name, 0x00000002, 0x00000000, 255, 65536, 65536, 0, None
            )
            if h_pipe == INVALID_HANDLE_VALUE:
                time.sleep(0.1)
                continue
            connected = kernel32.ConnectNamedPipe(h_pipe, None)
            if connected or kernel32.GetLastError() == 535:
                try:
                    written = wintypes.DWORD(0)
                    kernel32.WriteFile(h_pipe, data, len(data), ctypes.byref(written), None)
                    kernel32.FlushFileBuffers(h_pipe)
                except: pass
                finally: kernel32.DisconnectNamedPipe(h_pipe)
            kernel32.CloseHandle(h_pipe)

    def _serve_pipe_posix(self, pipe_path, data):
        while not self._sub_stop_evt.is_set():
            try:
                fd = os.open(pipe_path, os.O_WRONLY)
                os.write(fd, data)
                os.close(fd)
            except OSError:
                time.sleep(0.1)

    def _setup_sub_pipe(self, data):
        self._sub_stop_evt.clear()
        self._sub_data = data
        if _W:
            pipe_name = f"\\\\.\\pipe\\pplayer_sub_{uuid.uuid4().hex}"
            self._sub_pipe_name = pipe_name
            self._sub_thread = threading.Thread(target=self._serve_pipe_windows, args=(pipe_name, data), daemon=True)
            self._sub_thread.start()
            return pipe_name
        else:
            tmp_dir = tempfile.gettempdir()
            pipe_name = os.path.join(tmp_dir, f"pplayer_sub_{uuid.uuid4().hex}")
            try: os.mkfifo(pipe_name)
            except OSError: return None
            self._sub_pipe_name = pipe_name
            self._sub_thread = threading.Thread(target=self._serve_pipe_posix, args=(pipe_name, data), daemon=True)
            self._sub_thread.start()
            return pipe_name

    def _sub_embed(self, stream_idx, codec=""):
        self._cleanup_sub_pipe()
        was_playing = self._playing
        if was_playing: self._kill()
        
        data = self._extract_subtitle_to_mem(stream_idx, codec)
        if data and len(data) > 0:
            pipe_path = self._setup_sub_pipe(data)
            if pipe_path:
                self._sub_mode = "pipe"
                self._sub_ext_path = pipe_path
            else:
                self._sub_mode = "off"
        else:
            self._sub_mode = "off"

        if was_playing: self._start(self._ct)
        elif self._paused: self._grab_frame(self._ct)
        else: self._show_hint()

    def _sub_load_ext(self):
        ft = "Subtitle (*.srt *.ass *.ssa *.sub *.vtt *.idx *.sup);;All (*.*)"
        p, _ = QFileDialog.getOpenFileName(self, self._S("sub_ext"), "", ft)
        if p:
            self._cleanup_sub_pipe()
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
        # FIX: Ensure dimensions are even for YUV420p compatibility if needed,
        # and ensure 4-byte alignment for QImage (width multiple of 4).
        # We scale to self._render_w/h which are calculated in _start.
        w = self._render_w
        h = self._render_h
        parts.append(f"scale={w}:{h}")

        path_to_use = None
        if self._sub_mode == "ext":
            path_to_use = self._sub_ext_path
        elif self._sub_mode == "pipe":
            path_to_use = self._sub_ext_path

        if path_to_use:
            safe = path_to_use.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            parts.append(f"subtitles='{safe}'")
        return ",".join(parts)

    def _open_video(self, path):
        self._do_close()
        if not self._fp: return
        info = _probe(self._fp, path)
        if info is None:
            self._alert(self._S("eo").format(path))
            return
        self._path = path
        self._info = info
        self._ct = 0.0
        self._bar.duration = info["duration"]
        self._bar.set_pos(0)
        self._pcache.clear()
        self._sub_mode = "off"
        self._sub_ext_path = None
        self._cleanup_sub_pipe()

        w, h = info["width"], info["height"]
        # FIX: Don't downscale too aggressively for preview/drag, but keep aspect
        if h > 1080:
            w = int(w * 1080 / h)
            h = 1080
        self._dw = w + (w % 2)
        self._dh = h + (h % 2)

        self.setWindowTitle(f"{os.path.basename(path)} — {self._S('title')}")
        self._build_menus()
        self._start(0.0)

    def _start(self, t):
        self._evt.clear()
        self._gen += 1
        gen = self._gen
        self._playing = True
        self._paused = False
        self._ct = t
        self._hwd = ""
        self._lhw.setText("")

        # FIX: Use native resolution (no downscaling) for maximum quality.
        iw, ih = self._info["width"], self._info["height"]
        
        target_w = iw
        target_h = ih
        
        # FIX: Ensure width is a multiple of 4 for QImage 32-bit alignment
        # This prevents the "skewed black and white" issue.
        target_w = (target_w + 3) & ~3 
        target_h = target_h + (target_h % 2) # Even height is good practice

        self._render_w = target_w
        self._render_h = target_h

        cmd = [self._ff]
        if self._hwm == "auto": cmd += ["-hwaccel", "auto"]
        elif self._hwm != "off": cmd += ["-hwaccel", self._hwm]
        
        if t > 0.5: cmd += ["-ss", f"{t:.3f}"]
        cmd += ["-copyts", "-i", self._path, "-vf", self._build_vf_filter()]
        cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-an", "-sn", "-v", "error", "pipe:1"]
        
        bufsize = self._render_w * self._render_h * 3 * 2
        try:
            self._vp = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                bufsize=bufsize, **_pkw())
        except Exception as exc:
            self._alert(str(exc))
            self._playing = False
            return

        if self._info["has_audio"] and self._fy and not self._muted:
            self._audio.start(self._fy, self._ff, self._path, t, self._vol, self._speed)

        self._sync_t0 = t
        threading.Thread(target=self._vloop, args=(gen,), daemon=True).start()
        threading.Thread(target=self._detect_hw_thread, args=(gen,), daemon=True).start()
        self._bpp.setText("\u23F8")

    def _kill(self):
        self._evt.set()
        self._playing = False
        self._audio.stop()
        p = self._vp
        if p:
            self._vp = None
            try: p.kill()
            except: pass
            try: p.stdout.close()
            except: pass

    def _vloop(self, gen):
        proc = self._vp
        if not proc: return
        
        rw, rh = self._render_w, self._render_h
        fsz = rw * rh * 3
        fps = self._info["fps"]
        spf = 1.0 / fps
        speed = max(0.1, self._speed)
        dspf = spf / speed
        t0 = self._sync_t0
        has_audio = (self._info["has_audio"] and not self._muted and self._fy is not None)

        if has_audio: self._audio.wait_ready(timeout=3.0)
        wall0 = time.monotonic()
        n = 0
        first_frame = True

        try:
            while self._gen == gen and not self._evt.is_set():
                raw = _read_n(proc.stdout, fsz)
                if raw is None or self._gen != gen: break

                frame_time = t0 + n * spf
                self._ct = frame_time

                if first_frame:
                    first_frame = False
                    wall0 = time.monotonic()

                # Emit signal to UI thread immediately
                self.frameReady.emit(raw, rw, rh)

                a = self._audio
                use_audio = (has_audio and a.is_ready and a.is_alive and not self._muted)

                if use_audio:
                    for _ in range(1000):
                        if self._gen != gen or self._evt.is_set(): break
                        apos = a.media_position
                        if apos >= frame_time - 0.005: break
                        wait = min((frame_time - apos) / speed, 0.05)
                        if wait > 0.001: time.sleep(wait)
                        else: break
                    if self._gen != gen or self._evt.is_set(): break
                    apos = a.media_position
                    if apos > frame_time + spf * 4:
                        n += 1
                        continue
                    wall0 = time.monotonic() - n * dspf
                else:
                    target = wall0 + n * dspf
                    now = time.monotonic()
                    dt = target - now
                    if dt > 0.002: time.sleep(dt)
                    elif dt < -0.1:
                        if dt < -dspf * 5: wall0 = now - n * dspf
                        n += 1
                        continue
                n += 1
        except (OSError, ValueError): pass

        if self._gen == gen and not self._evt.is_set():
            self._playing = False
            # Signal EOF? For now just let tick handle it or user interaction

    def _on_frame_ready(self, data, w, h):
        # Convert bytes to QImage on GUI thread
        # QImage(bytes, width, height, format)
        # Note: We must keep a reference to data if QImage doesn't copy it.
        # But here we construct a new QImage which wraps the data.
        # To be safe from GC, we copy it into the widget's internal storage immediately.
        img = QImage(data, w, h, QImage.Format.Format_RGB888)
        # Copy is essential because 'data' is a local variable from signal
        self._cv.set_image(img.copy())

    def _detect_hw_thread(self, gen):
        if self._hwm == "off":
            if self._gen == gen: self.hwInfoReady.emit(self._S("stag"), "#aa6")
            return

        cmd = [self._ff, "-v", "verbose"]
        if self._hwm == "auto": cmd += ["-hwaccel", "auto"]
        else: cmd += ["-hwaccel", self._hwm]
        cmd += ["-i", self._path, "-frames:v", "1", "-f", "null", "-an", "-sn", "-"]
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, **_pkw())
            txt = r.stderr.decode("utf-8", errors="ignore")
        except: txt = ""

        if self._gen != gen: return

        hw_name = None
        for pat in [r"Using\s+auto\s+hwaccel\s+type\s+(\w+)", r"Using\s+(\w+)\s+hwaccel", r"hwaccel\s+type\s+(\w+)", r"HW\s+accel[:\s]+(\w+)", r"device\s+type[:\s]+(\w+)"]:
            m = re.search(pat, txt, re.I)
            if m:
                val = m.group(1)
                if val.lower() not in ("auto", "type", "with", "new"):
                    hw_name = val
                    break
        if not hw_name:
            m = re.search(r"(\w+(?:_cuvid|_qsv|_nvdec|_amf|_vaapi|_vdpau|_videotoolbox|_mediacodec|_d3d11va|_dxva2))", txt, re.I)
            if m: hw_name = m.group(1)
        
        if hw_name and self._gen == gen:
            self._hwd = hw_name
            self.hwInfoReady.emit(self._S("htag").format(hw_name), "#6a6")
        elif self._gen == gen:
            self.hwInfoReady.emit(self._S("stag"), "#aa6")

    def _on_hw_info(self, text, color):
        self._lhw.setText(text)
        self._lhw.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _tick(self):
        if self._playing:
            self._bar.set_pos(self._ct)
            self._tv.setText(f"{self._fmt(self._ct)} / {self._fmt(self._info['duration'])}")
        elif not self._playing and self._bpp.text() == "\u23F8":
             # EOF detection fallback
             self._on_eof()

    def _on_eof(self):
        self._bpp.setText("\u25B6")
        self._audio.stop()

    def _toggle_play(self):
        if not self._path: return
        if self._playing:
            self._kill()
            self._paused = True
            self._bpp.setText("\u25B6")
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
        self._bpp.setText("\u25B6")
        self._lhw.setText("")
        if self._info: self._tv.setText(f"00:00 / {self._fmt(self._info['duration'])}")
        else: self._tv.setText("00:00 / 00:00")

    def _do_close(self):
        self._kill()
        self._paused = False
        self._ct = 0.0
        self._path = None
        self._info = None
        self._cv.set_image(None)
        self._bar.duration = 0
        self._bar.set_pos(0)
        self._bpp.setText("\u25B6")
        self._lhw.setText("")
        self._tv.setText("00:00 / 00:00")
        self._sub_mode = "off"
        self._sub_ext_path = None
        self._cleanup_sub_pipe()
        self.setWindowTitle(self._S("title"))
        self._show_hint()

    def _on_drag_start(self):
        self._drag_was_playing = self._playing
        if self._playing: self._kill()
        self._bpp.setText("\u25B6")

    def _on_drag_preview(self, t):
        if not self._path or not self._info: return
        self._ct = t
        self._tv.setText(f"{self._fmt(t)} / {self._fmt(self._info['duration'])}")
        self._drag_gen += 1
        dg = self._drag_gen
        if self._drag_busy: return
        self._drag_busy = True
        dw, dh, path, ff = self._dw, self._dh, self._path, self._ff

        def job():
            cmd = [ff, "-ss", f"{t:.3f}", "-i", path, "-vframes", "1", "-f", "rawvideo",
                   "-pix_fmt", "rgb24", "-s", f"{dw}x{dh}", "-v", "quiet", "pipe:1"]
            data = _run_bin(cmd, timeout=3)
            need = dw * dh * 3
            if len(data) >= need:
                self.frameReady.emit(data[:need], dw, dh)
            self._drag_busy = False
            if self._drag_gen != dg and self._bar._dragging:
                newest_t = self._bar.position
                # Recurse via timer to avoid stack depth
                QTimer.singleShot(0, lambda: self._on_drag_preview(newest_t))

        threading.Thread(target=job, daemon=True).start()

    def _on_bar_release(self, t):
        was = self._drag_was_playing
        self._drag_was_playing = False
        self._ct = max(0.0, t)
        if was: self._start(self._ct)
        else:
            self._paused = True
            self._bar.set_pos(self._ct)
            if self._info: self._tv.setText(f"{self._fmt(self._ct)} / {self._fmt(self._info['duration'])}")
            self._grab_frame(self._ct)

    def _seek_rel(self, dt):
        if not self._info: return
        t = max(0.0, min(self._info["duration"], self._ct + dt))
        was = self._playing
        self._kill()
        self._ct = t
        if was: self._start(self._ct)
        else:
            self._paused = True
            self._bar.set_pos(self._ct)
            self._tv.setText(f"{self._fmt(self._ct)} / {self._fmt(self._info['duration'])}")
            self._grab_frame(self._ct)

    def _grab_frame(self, t):
        dw, dh, path, ff = self._dw, self._dh, self._path, self._ff
        vf = self._build_vf_filter()
        def job():
            cmd = [ff, "-ss", f"{t:.3f}", "-i", path, "-vf", vf, "-vframes", "1",
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-v", "quiet", "pipe:1"]
            data = _run_bin(cmd, timeout=5)
            need = dw * dh * 3
            if len(data) >= need:
                self.frameReady.emit(data[:need], dw, dh)
        threading.Thread(target=job, daemon=True).start()

    def _next_frame(self):
        if not self._info: return
        if self._playing:
            self._kill()
            self._paused = True
            self._bpp.setText("\u25B6")
        dt = 1.0 / self._info["fps"]
        self._ct = min(self._info["duration"], self._ct + dt)
        self._grab_frame(self._ct)
        self._bar.set_pos(self._ct)
        self._tv.setText(f"{self._fmt(self._ct)} / {self._fmt(self._info['duration'])}")

    def _set_speed(self, v):
        self._speed = v
        self._lsp.setText(f"{v}x")
        if self._playing:
            t = self._ct
            self._kill()
            self._start(t)

    def _cycle_speed(self, d):
        try: idx = self.SPEEDS.index(self._speed)
        except: idx = self.SPEEDS.index(1.0)
        idx = max(0, min(len(self.SPEEDS) - 1, idx + d))
        self._set_speed(self.SPEEDS[idx])

    def _on_vol(self, val):
        self._vol = val
        self._muted = False
        self._lvl.setText(f"{self._vol}%")
        self._mu_icon()
        if self._vol_timer:
            self._vol_timer.stop()
            self._vol_timer = None
        if self._playing and self._info and self._info["has_audio"] and self._fy:
            self._vol_timer = QTimer()
            self._vol_timer.setSingleShot(True)
            self._vol_timer.timeout.connect(self._restart_audio_vol)
            self._vol_timer.start(300)

    def _restart_audio_vol(self):
        self._vol_timer = None
        if self._playing and self._info and self._info["has_audio"] and self._fy and not self._muted:
            self._audio.start(self._fy, self._ff, self._path, self._ct, self._vol, self._speed)

    def _chg_vol(self, d):
        self._vol = max(0, min(100, self._vol + d))
        self._vsc.setValue(self._vol)

    def _toggle_mute(self):
        self._muted = not self._muted
        self._mu_icon()
        if self._muted: self._audio.stop()
        elif self._playing and self._info and self._info["has_audio"] and self._fy:
            self._audio.start(self._fy, self._ff, self._path, self._ct, self._vol, self._speed)

    def _mu_icon(self):
        if self._muted or self._vol == 0: self._bmu.setText("\U0001F507")
        elif self._vol < 50: self._bmu.setText("\U0001F509")
        else: self._bmu.setText("\U0001F50A")

    def _toggle_fs(self):
        self._fsc = not self._fsc
        if self._fsc:
            self.showFullScreen()
            self.menuBar().hide()
            self._ctrl.hide()
        else:
            self.showNormal()
            self.menuBar().show()
            self._ctrl.show()

    def _prev_hover(self, t, gx, gy):
        if not self._info or not self._path: return
        key = int(t * 2)
        if key in self._pcache:
            self._tip.show_tip(self._pcache[key], self._fmt(t), gx, gy)
            return
        if self._pbusy: return
        self._pbusy = True
        path, ff = self._path, self._ff
        iw, ih = self._info["width"], self._info["height"]
        
        def job():
            pw = 160
            ph = max(2, int(pw * ih / max(1, iw)))
            ph += ph % 2
            cmd = [ff, "-ss", f"{t:.3f}", "-i", path, "-vframes", "1", "-f", "rawvideo",
                   "-pix_fmt", "rgb24", "-s", f"{pw}x{ph}", "-v", "quiet", "pipe:1"]
            try:
                data = _run_bin(cmd, timeout=3)
                need = pw * ph * 3
                if len(data) >= need:
                    img = QImage(data[:need], pw, ph, QImage.Format.Format_RGB888).copy()
                    self.previewReady.emit(key, img)
            except: pass
            finally: self._pbusy = False
        threading.Thread(target=job, daemon=True).start()

    def _on_preview_ready(self, key, img):
        if len(self._pcache) > 200: self._pcache.clear()
        self._pcache[key] = img
        # If mouse is still hovering, update tip? 
        # Simplified: just let next hover event pick it up or user moves mouse slightly
        # But we can try to show it if bar is still hovered.
        # For now, rely on mouse move to re-trigger cache hit.

    def _prev_leave(self):
        self._tip.hide()

    def _set_boss(self):
        d = QDialog(self)
        d.setWindowTitle(self._S("boss"))
        d.setFixedSize(340, 110)
        l = QVBoxLayout(d)
        lbl = QLabel(self._S("bp").format(self._boss))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(lbl)
        
        def keyPress(e):
            self._boss = QKeySequence(e.key()).toString()
            d.accept()
        d.keyPressEvent = keyPress
        d.exec()

    def _set_hw(self, mode):
        self._hwm = mode
        if self._playing:
            t = self._ct
            self._kill()
            self._start(t)
    
    def _set_opacity(self, pct):
        self._opacity = max(0.3, min(1.0, pct / 100.0))
        self.setWindowOpacity(self._opacity)

    def _about(self):
        d = QDialog(self)
        d.setWindowTitle(self._S("about"))
        d.setFixedSize(480, 340)
        l = QVBoxLayout(d)
        
        ver_line = "unknown"
        try:
            ver_raw = _run_text([self._ff, "-version"], timeout=5)
            if ver_raw: ver_line = ver_raw.strip().split("\n")[0]
        except: pass
        
        txt = self._S("abt") + f"\n\n{ver_line}"
        if self._fp: txt += f"\nffprobe: {self._fp}"
        if self._fy: txt += f"\nffplay: {self._fy}"
        else: txt += "\nffplay: (not found — no audio)"
        
        lbl = QLabel(txt)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        l.addWidget(lbl)
        
        btn = QPushButton(self._S("ok"))
        btn.clicked.connect(d.accept)
        l.addWidget(btn)
        d.exec()

    def _alert(self, msg):
        d = QDialog(self)
        d.setWindowTitle("!")
        d.setFixedSize(420, 140)
        l = QVBoxLayout(d)
        lbl = QLabel(msg)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        l.addWidget(lbl)
        btn = QPushButton(self._S("ok"))
        btn.clicked.connect(d.accept)
        l.addWidget(btn)
        d.exec()

    def closeEvent(self, event):
        self._save_settings()
        self._kill()
        self._cleanup_sub_pipe()
        event.accept()

# Helper for Input Dialog
def QInputDialog_getText(parent, title, label):
    d = QDialog(parent)
    d.setWindowTitle(title)
    l = QVBoxLayout(d)
    l.addWidget(QLabel(label))
    le = QLineEdit()
    l.addWidget(le)
    btns = QHBoxLayout()
    ok = QPushButton("OK")
    ok.clicked.connect(d.accept)
    cancel = QPushButton("Cancel")
    cancel.clicked.connect(d.reject)
    btns.addWidget(ok)
    btns.addWidget(cancel)
    l.addLayout(btns)
    if d.exec() == QDialog.DialogCode.Accepted:
        return le.text(), True
    return "", False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Player()
    player.show()
    if len(sys.argv) > 1:
        p = sys.argv[1]
        if os.path.isfile(p):
            QTimer.singleShot(300, lambda: player._open_video(p))
    sys.exit(app.exec())
