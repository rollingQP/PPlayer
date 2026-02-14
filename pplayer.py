#!/usr/bin/env python3
"""
PPlayer — High Performance FFmpeg video player (OpenGL).
Refactored for 4K playback without quality loss.
Required : Python 3.7+, Pillow, PyQt6, PyOpenGL
Install  : pip install PyQt6 Pillow PyOpenGL
"""

import sys
import os
import time
import json
import shutil
import subprocess
import threading
import re
import platform
import atexit
from pathlib import Path

# ── Dependency Checks ──────────────────────────────────────
try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required.\nRun: pip install Pillow")
    sys.exit(1)

try:
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, 
                                 QVBoxLayout, QHBoxLayout, QFileDialog, QMenu, 
                                 QSlider, QPushButton, QFrame, QDialog, QLineEdit,
                                 QToolTip, QSizePolicy)
    from PyQt6.QtCore import (Qt, QTimer, pyqtSignal, QObject, QEvent, QPoint, 
                              QSize, QRect, QBuffer, QByteArray)
    from PyQt6.QtGui import (QImage, QPixmap, QPainter, QColor, QAction, 
                             QKeySequence, QIcon, QFont, QCursor, QScreen,
                             QSurfaceFormat)
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget
    from PyQt6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram
except ImportError:
    print("Error: PyQt6 is required.\nRun: pip install PyQt6")
    sys.exit(1)

try:
    import OpenGL.GL as gl
except ImportError:
    print("Error: PyOpenGL is required for hardware rendering.\nRun: pip install PyOpenGL")
    sys.exit(1)

_W = platform.system() == "Windows"

# ── Global Cleanup for Zombie Processes ─────────────────────
_ACTIVE_PROCESSES = set()

def _register_proc(proc):
    if proc: _ACTIVE_PROCESSES.add(proc)

def _unregister_proc(proc):
    if proc in _ACTIVE_PROCESSES: _ACTIVE_PROCESSES.discard(proc)

def _cleanup_all_processes():
    for p in list(_ACTIVE_PROCESSES):
        try:
            p.terminate()
            p.wait(timeout=0.2)
        except:
            try: p.kill()
            except: pass

atexit.register(_cleanup_all_processes)

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
        "abt": "PPlayer (OpenGL)\nHigh-performance FFmpeg player.",
        "hint": "Drop a video file here\nor use File → Open",
        "htag": "HW: {}",
        "stag": "SW Decode",
        "noff": "FFmpeg not found!",
        "ep": "Enter file path or URL:",
        "bp": "Press a key to set as new boss key.\nCurrent: {}",
        "eo": "Cannot open:\n{}",
        "ok": "OK",
        "cancel": "Cancel",
        "sub_extracting": "Loading subtitles...",
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
        "abt": "PPlayer (OpenGL)\n高性能 FFmpeg 播放器。",
        "hint": "拖放视频文件到此处\n或使用 文件→打开",
        "htag": "硬解: {}",
        "stag": "软件解码",
        "noff": "未找到 FFmpeg！",
        "ep": "输入文件路径或 URL：",
        "bp": "按下一个键设为新的老板键\n当前：{}",
        "eo": "无法打开：\n{}",
        "ok": "确定",
        "cancel": "取消",
        "sub_extracting": "正在加载字幕...",
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
    if local_path.is_file(): return str(local_path)
    system_path = shutil.which(name)
    if system_path: return system_path
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
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, **_pkw())
        return r.stdout.decode("utf-8", errors="ignore")
    except: return ""

def _probe(ffprobe, path):
    txt = _run_text([ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path], timeout=15)
    if not txt: return None
    try: d = json.loads(txt)
    except: return None
    info = dict(duration=0.0, width=0, height=0, fps=30.0, has_audio=False, subs=[])
    info["duration"] = float(d.get("format", {}).get("duration", 0))
    sub_idx = 0
    for s in d.get("streams", []):
        ct = s.get("codec_type")
        if ct == "video" and info["width"] == 0:
            info["width"] = int(s.get("width", 0))
            info["height"] = int(s.get("height", 0))
            try:
                fr = s.get("r_frame_rate", "30/1")
                if "/" in fr:
                    n, dd = fr.split("/")
                    info["fps"] = float(n) / max(1, float(dd))
                else: info["fps"] = float(fr)
            except: pass
            if not (0 < info["fps"] <= 240): info["fps"] = 30.0
        elif ct == "audio": info["has_audio"] = True
        elif ct == "subtitle":
            tags = s.get("tags", {})
            lang = tags.get("language", tags.get("title", f"#{sub_idx}"))
            title = tags.get("title", "")
            label = f"#{sub_idx}"
            if title: label += f" {title}"
            if lang and lang != title: label += f" ({lang})"
            info["subs"].append({"index": int(s.get("index", sub_idx)), "stream_idx": sub_idx, "label": label})
            sub_idx += 1
    return info if info["width"] > 0 else None

def _hwaccels(ffmpeg):
    txt = _run_text([ffmpeg, "-hwaccels"], timeout=5)
    return [l.strip() for l in txt.strip().split("\n")[1:] if l.strip()]

def _read_n(pipe, n):
    buf = b""
    while len(buf) < n:
        ch = pipe.read(n - len(buf))
        if not ch: return None
        buf += ch
    return buf

# ━━━━━━━━━━━━━━━ Audio Player ━━━━━━━━━━━━━━━
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

    def start(self, ffplay, ffmpeg, path, seek, vol, speed):
        self.stop()
        self._speed = max(0.1, speed)
        self._seek_time = seek
        with self._lock:
            self._pos = seek
            self._pos_wall = time.monotonic()
        self._ready.clear()
        self._alive = True
        
        cmd_src = [ffmpeg, "-ss", f"{seek:.3f}", "-i", path, "-vn", "-f", "wav", "-"]
        cmd_play = [ffplay, "-nodisp", "-autoexit", "-vn", "-loglevel", "info", "-volume", str(vol)]
        if abs(speed - 1.0) > 0.01:
            parts = []
            v = speed
            while v > 2.0: parts.append("atempo=2.0"); v /= 2.0
            while v < 0.5: parts.append("atempo=0.5"); v *= 2.0
            parts.append(f"atempo={v:.4f}")
            cmd_play += ["-af", ",".join(parts)]
        cmd_play += ["-i", "-"]

        try:
            self._proc_src = subprocess.Popen(cmd_src, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **_pkw())
            self._proc = subprocess.Popen(cmd_play, stdin=self._proc_src.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **_pkw())
            self._proc_src.stdout.close()
            _register_proc(self._proc_src)
            _register_proc(self._proc)
        except:
            self._alive = False
            return
        threading.Thread(target=self._reader, daemon=True).start()

    def stop(self):
        self._alive = False
        self._ready.clear()
        for p in [self._proc, self._proc_src]:
            if p:
                _unregister_proc(p)
                try: p.terminate()
                except: pass
                try: p.wait(0.2)
                except: 
                    try: p.kill()
                    except: pass
        self._proc = None
        self._proc_src = None

    def wait_ready(self, timeout=5.0): return self._ready.wait(timeout)
    @property
    def is_ready(self): return self._ready.is_set()
    @property
    def is_alive(self): return (self._alive and self._proc and self._proc.poll() is None)
    @property
    def media_position(self):
        with self._lock:
            if not self._ready.is_set(): return self._seek_time
            elapsed = time.monotonic() - self._pos_wall
            interp = self._pos + elapsed
            if abs(self._speed - 1.0) < 0.01: return interp
            return self._seek_time + (interp - self._seek_time) * self._speed

    def _reader(self):
        proc = self._proc
        if not proc: return
        buf = b""
        try:
            while proc.poll() is None:
                ch = proc.stderr.read(1)
                if not ch: break
                if ch in (b'\r', b'\n'):
                    if buf:
                        m = re.search(r'([\d]+\.[\d]+).*?fd=', buf.decode("utf-8", "ignore"))
                        if m:
                            try:
                                raw = float(m.group(1))
                                with self._lock:
                                    self._pos = raw + self._seek_time
                                    self._pos_wall = time.monotonic()
                                if not self._ready.is_set(): self._ready.set()
                            except: pass
                        buf = b""
                else: buf += ch
        except: pass
        self._alive = False

# ━━━━━━━━━━━━━━━ OpenGL Video Widget ━━━━━━━━━━━━━━━━━━━
class YUVOpenGLWidget(QOpenGLWidget):
    doubleClicked = pyqtSignal()
    clicked = pyqtSignal()
    wheelScrolled = pyqtSignal(int)

    VERTEX_SHADER = """
        attribute vec4 vertexIn;
        attribute vec2 textureIn;
        varying vec2 textureOut;
        void main(void) {
            gl_Position = vertexIn;
            textureOut = textureIn;
        }
    """

    FRAGMENT_SHADER = """
        varying vec2 textureOut;
        uniform sampler2D tex_y;
        uniform sampler2D tex_u;
        uniform sampler2D tex_v;
        void main(void) {
            vec3 yuv;
            vec3 rgb;
            yuv.x = texture2D(tex_y, textureOut).r;
            yuv.y = texture2D(tex_u, textureOut).r - 0.5;
            yuv.z = texture2D(tex_v, textureOut).r - 0.5;
            rgb = mat3( 1,       1,         1,
                        0,       -0.39465,  2.03211,
                        1.13983, -0.58060,  0) * yuv;
            gl_FragColor = vec4(rgb, 1);
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._y_data = None
        self._u_data = None
        self._v_data = None
        self._w = 0
        self._h = 0
        self._program = None
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(lambda: self.clicked.emit())
        self._text = ""
        self._textures = [0, 0, 0]

    def set_frame(self, y_data, u_data, v_data, w, h):
        self._y_data = y_data
        self._u_data = u_data
        self._v_data = v_data
        self._w = w
        self._h = h
        self._text = ""
        self.update()

    def set_text(self, text):
        self._text = text
        self._y_data = None
        self.update()

    def initializeGL(self):
        self._program = QOpenGLShaderProgram(self)
        self._program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, self.VERTEX_SHADER)
        self._program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, self.FRAGMENT_SHADER)
        self._program.link()
        self._textures = gl.glGenTextures(3)

    def paintGL(self):
        painter = QPainter(self)
        painter.beginNativePainting()
        
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        if self._y_data and self._w > 0:
            self._program.bind()
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
            
            def upload_tex(idx, tid, w, h, data):
                gl.glActiveTexture(gl.GL_TEXTURE0 + idx)
                gl.glBindTexture(gl.GL_TEXTURE_2D, tid)
                gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_LUMINANCE, w, h, 0, gl.GL_LUMINANCE, gl.GL_UNSIGNED_BYTE, data)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)

            upload_tex(0, self._textures[0], self._w, self._h, self._y_data)
            upload_tex(1, self._textures[1], self._w//2, self._h//2, self._u_data)
            upload_tex(2, self._textures[2], self._w//2, self._h//2, self._v_data)

            self._program.setUniformValue("tex_y", 0)
            self._program.setUniformValue("tex_u", 1)
            self._program.setUniformValue("tex_v", 2)

            # FIX: Use list of tuples for PyQt6 setAttributeArray
            vertices = [
                (-1.0, -1.0),
                ( 1.0, -1.0),
                (-1.0,  1.0),
                ( 1.0,  1.0)
            ]
            texCoords = [
                (0.0, 1.0),
                (1.0, 1.0),
                (0.0, 0.0),
                (1.0, 0.0)
            ]
            
            loc_v = self._program.attributeLocation("vertexIn")
            loc_t = self._program.attributeLocation("textureIn")
            
            self._program.enableAttributeArray(loc_v)
            self._program.enableAttributeArray(loc_t)
            
            # Pass list of tuples directly. No tuple size argument needed for this overload.
            self._program.setAttributeArray(loc_v, vertices)
            self._program.setAttributeArray(loc_t, texCoords)
            
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            
            self._program.disableAttributeArray(loc_v)
            self._program.disableAttributeArray(loc_t)
            self._program.release()
        
        painter.endNativePainting()

        if self._text:
            painter.setPen(QColor("#888888"))
            font = painter.font()
            font.setPointSize(16)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self._click_timer.start(300)
        elif event.button() == Qt.MouseButton.BackButton: self.wheelScrolled.emit(5)
        elif event.button() == Qt.MouseButton.ForwardButton: self.wheelScrolled.emit(-5)

    def mouseDoubleClickEvent(self, event):
        self._click_timer.stop()
        self.doubleClicked.emit()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0: self.wheelScrolled.emit(5)
        else: self.wheelScrolled.emit(-5)

# ━━━━━━━━━━━━━━━ UI Components ━━━━━━━━━━━━━━━━━━━
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
        painter.fillRect(4, cy - 3, w - 8, 6, QColor("#444444"))
        if self.duration > 0:
            ratio = self.position / self.duration
            px = int(4 + (w - 8) * ratio)
            px = max(4, min(w - 4, px))
            painter.fillRect(4, cy - 3, px - 4, 6, QColor("#0078d4"))
            painter.setBrush(Qt.GlobalColor.white)
            painter.setPen(QColor("#0078d4"))
            painter.drawEllipse(QPoint(px, cy), 6, 6)

    def _time_at_x(self, x):
        w = self.width()
        if self.duration <= 0 or w <= 8: return 0.0
        return max(0.0, min(self.duration, ((x - 4) / (w - 8)) * self.duration))

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
                gp = event.globalPosition().toPoint()
                self.hoverMove.emit(t, gp.x(), gp.y())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.position = self._time_at_x(event.pos().x())
            self.update()
            self.seekRequested.emit(self.position)

    def leaveEvent(self, event): self.hoverLeave.emit()

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
        w, h = pix.width(), pix.height() + 20
        nx = gx - w // 2
        ny = gy - h - 40
        
        screen = QApplication.screenAt(QPoint(gx, gy))
        if not screen: screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            nx = max(geo.left(), min(nx, geo.right() - w))
            if ny < geo.top(): ny = gy + 20
            ny = max(geo.top(), min(ny, geo.bottom() - h))
            
        self.move(nx, ny)
        self.show()

# ━━━━━━━━━━━━━━━━━━ Player Logic ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Player(QMainWindow):
    frameReady = pyqtSignal(bytes, bytes, bytes, int, int) 
    hwInfoReady = pyqtSignal(str, str)
    previewReady = pyqtSignal(int, object)

    SPEEDS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]

    def __init__(self):
        super().__init__()
        self._ff = _find("ffmpeg")
        self._fp = _find("ffprobe")
        self._fy = _find("ffplay")

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
        self._dw = 0 # FIX: Initialize _dw
        self._dh = 0 # FIX: Initialize _dh
        self._sub_mode = "off"
        self._sub_ext_path = None
        self._sub_stream_idx = -1

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
        
        self.frameReady.connect(self._on_frame_ready)
        self.hwInfoReady.connect(self._on_hw_info)
        self.previewReady.connect(self._on_preview_ready)

        self._vsc.setValue(self._vol)
        self._lsp.setText(f"{self._speed}x")
        self._mu_icon()

        QTimer.singleShot(250, self._show_hint)
        self._tick_timer = QTimer()
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(50)

    def _S(self, k): return _L.get(self._lang, _L["en"]).get(k, k)
    @staticmethod
    def _fmt(s):
        s = max(0, int(s))
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        return f"{h}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"

    def _show_hint(self): self._cv.set_text(self._S("hint"))

    def _load_settings(self):
        defaults = dict(lang="en", volume=100, speed=1.0, hw_mode="auto", boss_key="Escape", boss_any=False, opacity=1.0, geometry="800x500")
        try:
            if _CFG_FILE.exists():
                with open(_CFG_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    for k in defaults:
                        if k in d: defaults[k] = d[k]
        except: pass
        if defaults["lang"] not in _L: defaults["lang"] = "en"
        return defaults

    def _save_settings(self):
        try:
            _CFG_DIR.mkdir(parents=True, exist_ok=True)
            d = dict(lang=self._lang, volume=self._vol, speed=self._speed, hw_mode=self._hwm, boss_key=self._boss, boss_any=self._boss_any, opacity=self._opacity, geometry=f"{self.width()}x{self.height()}")
            with open(_CFG_FILE, "w", encoding="utf-8") as f: json.dump(d, f, indent=2)
        except: pass

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._cv = YUVOpenGLWidget()
        self._cv.clicked.connect(self._toggle_play)
        self._cv.doubleClicked.connect(self._toggle_fs)
        self._cv.wheelScrolled.connect(self._chg_vol)
        main_layout.addWidget(self._cv, 1)

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
        B_STYLE = "QPushButton { background-color: #181818; color: white; border: none; font-family: 'Segoe UI Symbol'; font-size: 16px; padding: 4px; } QPushButton:hover { background-color: #333; }"
        
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
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut: action.setShortcut(QKeySequence(shortcut))
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
        for s in self.SPEEDS: self._add_action(msp, f"{s}x", lambda v=s: self._set_speed(v))
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
                self._add_action(msub, sub["label"], lambda idx=sub["stream_idx"]: self._sub_embed(idx))
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
        for a in _hwaccels(self._ff): self._add_action(mhw, a, lambda v=a: self._set_hw(v))
        mop = ms.addMenu(S("opa"))
        for p in (100, 90, 80, 70, 60, 50, 40, 30): self._add_action(mop, f"{p}%", lambda v=p: self._set_opacity(v))
        mh = mb.addMenu(S("help"))
        self._add_action(mh, S("about"), self._about)

    def keyPressEvent(self, event):
        key = event.key()
        try:
            ks = QKeySequence(key).toString()
            if ks.lower() == self._boss.lower() or (self._boss == "Escape" and key == Qt.Key.Key_Escape):
                self.close(); return
        except: pass
        if self._boss_any and key not in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            if not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
                self.close(); return
        if key == Qt.Key.Key_F11: self._toggle_fs()
        elif key == Qt.Key.Key_BracketRight: self._cycle_speed(1)
        elif key == Qt.Key.Key_BracketLeft: self._cycle_speed(-1)
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files: self._open_video(files[0])

    def _toggle_boss_any(self, checked): self._boss_any = checked
    def _set_lang(self, c):
        self._lang = c
        self._apply_lang()
        if not self._playing and not self._path: self._show_hint()
    def _apply_lang(self):
        self.setWindowTitle(f"{os.path.basename(self._path)} — {self._S('title')}" if self._path else self._S("title"))
        self._build_menus()

    def _open_file(self):
        p, _ = QFileDialog.getOpenFileName(self, self._S("open"), "", "Video (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm);;All (*.*)")
        if p: self._open_video(p)
    def _open_path(self):
        text, ok = QInputDialog_getText(self, self._S("open_path"), self._S("ep"))
        if ok and text: self._open_video(text.strip())

    def _sub_off(self):
        if self._sub_mode != "off":
            self._sub_mode = "off"
            self._sub_ext_path = None
            self._sub_stream_idx = -1
            if self._playing: self._start(self._ct)

    def _sub_embed(self, stream_idx):
        self._sub_mode = "embed"
        self._sub_stream_idx = stream_idx
        self._sub_ext_path = None
        if self._playing: self._start(self._ct)
        elif self._paused: self._grab_frame(self._ct)

    def _sub_load_ext(self):
        p, _ = QFileDialog.getOpenFileName(self, self._S("sub_ext"), "", "Subtitle (*.srt *.ass *.ssa *.vtt);;All (*.*)")
        if p:
            self._sub_mode = "ext"
            self._sub_ext_path = p
            self._sub_stream_idx = -1
            if self._playing: self._start(self._ct)
            elif self._paused: self._grab_frame(self._ct)

    def _escape_filter_path(self, path):
        return path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'").replace("[", "\\[").replace("]", "\\]")

    def _build_vf_filter(self):
        parts = []
        # Subtitles
        if self._sub_mode == "embed" and self._sub_stream_idx >= 0:
            safe_path = self._escape_filter_path(self._path)
            parts.append(f"subtitles=filename='{safe_path}':stream_index={self._sub_stream_idx}")
        elif self._sub_mode == "ext" and self._sub_ext_path:
            safe_path = self._escape_filter_path(self._sub_ext_path)
            parts.append(f"subtitles=filename='{safe_path}'")
        
        # IMPORTANT: No scaling here! We output native resolution.
        # But we must ensure dimensions are even for YUV420P
        parts.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
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
        self._sub_stream_idx = -1
        
        # FIX: Calculate display width/height for drag preview
        w, h = info["width"], info["height"]
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

        # Native resolution
        iw, ih = self._info["width"], self._info["height"]
        self._render_w = iw - (iw % 2)
        self._render_h = ih - (ih % 2)

        cmd = [self._ff]
        if self._hwm == "auto": cmd += ["-hwaccel", "auto"]
        elif self._hwm != "off": cmd += ["-hwaccel", self._hwm]
        
        if t > 0.5: cmd += ["-ss", f"{t:.3f}"]
        
        # Output YUV420P raw video. Much smaller than RGB.
        cmd += ["-copyts", "-i", self._path, "-vf", self._build_vf_filter()]
        cmd += ["-f", "rawvideo", "-pix_fmt", "yuv420p", "-an", "-sn", "-v", "error", "pipe:1"]
        
        # Buffer size: YUV420P is 1.5 bytes per pixel
        bufsize = int(self._render_w * self._render_h * 1.5 * 4)
        try:
            self._vp = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=bufsize, **_pkw())
            _register_proc(self._vp)
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
            _unregister_proc(p)
            self._vp = None
            try: p.kill()
            except: pass
            try: p.stdout.close()
            except: pass

    def _vloop(self, gen):
        proc = self._vp
        if not proc: return
        
        w, h = self._render_w, self._render_h
        # YUV420P sizes
        y_sz = w * h
        uv_sz = (w // 2) * (h // 2)
        frame_sz = y_sz + 2 * uv_sz
        
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
                # Read YUV planes
                raw = _read_n(proc.stdout, frame_sz)
                if raw is None or self._gen != gen: break

                frame_time = t0 + n * spf
                self._ct = frame_time

                if first_frame:
                    first_frame = False
                    wall0 = time.monotonic()

                a = self._audio
                use_audio = (has_audio and a.is_ready and a.is_alive and not self._muted)

                if use_audio:
                    apos = a.media_position
                    # Drop frame if video is too late (> 0.4s)
                    if apos > frame_time + 0.4:
                        n += 1
                        continue

                    # Split planes
                    y_plane = raw[:y_sz]
                    u_plane = raw[y_sz:y_sz+uv_sz]
                    v_plane = raw[y_sz+uv_sz:]
                    self.frameReady.emit(y_plane, u_plane, v_plane, w, h)

                    for _ in range(1000):
                        if self._gen != gen or self._evt.is_set(): break
                        apos = a.media_position
                        if apos >= frame_time - 0.02: break
                        wait = min((frame_time - apos) / speed, 0.05)
                        if wait > 0.001: time.sleep(wait)
                        else: break
                    
                    if self._gen != gen or self._evt.is_set(): break
                    
                    apos = a.media_position
                    if abs(apos - frame_time) > 2.0:
                        n = int((apos - t0) / spf)
                        wall0 = time.monotonic() - n * dspf
                else:
                    y_plane = raw[:y_sz]
                    u_plane = raw[y_sz:y_sz+uv_sz]
                    v_plane = raw[y_sz+uv_sz:]
                    self.frameReady.emit(y_plane, u_plane, v_plane, w, h)
                    
                    target = wall0 + n * dspf
                    now = time.monotonic()
                    dt = target - now
                    if dt > 0.002: time.sleep(dt)
                    elif dt < -0.1:
                        if dt < -dspf * 5: wall0 = now - n * dspf
                n += 1
        except: pass
        if self._gen == gen and not self._evt.is_set(): self._playing = False

    def _on_frame_ready(self, y, u, v, w, h):
        self._cv.set_frame(y, u, v, w, h)

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
        elif not self._playing and self._bpp.text() == "\u23F8": self._on_eof()

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
        else: self._start(0.0)

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
        self._cv.set_frame(None, None, None, 0, 0)
        self._bar.duration = 0
        self._bar.set_pos(0)
        self._bpp.setText("\u25B6")
        self._lhw.setText("")
        self._tv.setText("00:00 / 00:00")
        self._sub_mode = "off"
        self._sub_ext_path = None
        self._sub_stream_idx = -1
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
            cmd = [ff, "-ss", f"{t:.3f}", "-i", path, "-vframes", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{dw}x{dh}", "-v", "quiet", "pipe:1"]
            data = _run_bin(cmd, timeout=3)
            need = dw * dh * 3
            if len(data) >= need:
                # Preview still uses RGB for simplicity in tooltip
                img = QImage(data[:need], dw, dh, QImage.Format.Format_RGB888).copy()
                self.previewReady.emit(0, img) # Key 0 for drag preview
            self._drag_busy = False
            if self._drag_gen != dg and self._bar._dragging:
                QTimer.singleShot(0, lambda: self._on_drag_preview(self._bar.position))
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
        # For static grab, we can use RGB for simplicity or YUV. Let's stick to YUV for consistency.
        vf = self._build_vf_filter()
        w, h = self._render_w, self._render_h
        y_sz = w * h
        uv_sz = (w // 2) * (h // 2)
        frame_sz = y_sz + 2 * uv_sz
        path, ff = self._path, self._ff
        def job():
            cmd = [ff, "-ss", f"{t:.3f}", "-i", path, "-vf", vf, "-vframes", "1", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-v", "quiet", "pipe:1"]
            data = _run_bin(cmd, timeout=5)
            if len(data) >= frame_sz:
                self.frameReady.emit(data[:y_sz], data[y_sz:y_sz+uv_sz], data[y_sz+uv_sz:], w, h)
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
        if self._playing: self._start(self._ct)

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
        if self._vol_timer: self._vol_timer.stop(); self._vol_timer = None
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
        # Preview logic: still use RGB for simplicity in tooltip (small size)
        def job():
            pw = 160
            ph = max(2, int(pw * ih / max(1, iw)))
            ph += ph % 2
            cmd = [ff, "-ss", f"{t:.3f}", "-i", path, "-vframes", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{pw}x{ph}", "-v", "quiet", "pipe:1"]
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
        if key == 0: return # Drag preview handled elsewhere
        if len(self._pcache) > 200: self._pcache.clear()
        self._pcache[key] = img

    def _prev_leave(self): self._tip.hide()

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
        if self._playing: self._start(self._ct)
    
    def _set_opacity(self, pct):
        self._opacity = max(0.3, min(1.0, pct / 100.0))
        self.setWindowOpacity(self._opacity)

    def _about(self):
        d = QDialog(self)
        d.setWindowTitle(self._S("about"))
        d.setFixedSize(480, 340)
        l = QVBoxLayout(d)
        ver_line = "unknown"
        try: ver_line = _run_text([self._ff, "-version"], timeout=5).split("\n")[0]
        except: pass
        txt = self._S("abt") + f"\n\n{ver_line}"
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
        event.accept()

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
    if d.exec() == QDialog.DialogCode.Accepted: return le.text(), True
    return "", False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Player()
    player.show()
    if len(sys.argv) > 1:
        p = sys.argv[1]
        if os.path.isfile(p): QTimer.singleShot(300, lambda: player._open_video(p))
    sys.exit(app.exec())
