"""
video_compressor.py  ─  Video Compressor Pro (GUI)
================================================================
기능:
  - 파일/폴더 열기로 영상 추가
  - H.265 (HEVC) + CRF 방식 압축
  - 해상도 축소 (lanczos 필터)
  - 출력: 원본폴더/Comp 또는 사용자 지정 폴더
  - 압축 후 원본 삭제 옵션
  - 진행률 실시간 표시
  - 로그 패널

지원 형식:
  MP4 MOV AVI MKV WMV FLV M4V TS MTS M2TS WEBM
  3GP DV OGV MPG MPEG VOB RM RMVB ASF DIVX F4V
================================================================
"""

import os
import sys
import shutil
import subprocess
import threading
import queue
import time
from pathlib import Path
from datetime import timedelta

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# ──────────────────────────────────────────────────────────────
#  상수 / 설정
# ──────────────────────────────────────────────────────────────

APP_TITLE   = "🎬 Video Compressor Pro"
APP_VERSION = "1.0.0"
APP_DIR     = Path(__file__).parent

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v",
    ".ts", ".mts", ".m2ts", ".webm", ".3gp", ".dv", ".ogv",
    ".mpg", ".mpeg", ".vob", ".rm", ".rmvb", ".asf", ".divx",
    ".f4v", ".xvid",
}

RESOLUTIONS = {
    "원본 유지": None,
    "4K  (3840)": "3840:-2",
    "FHD (1920)": "1920:-2",
    "HD  (1280)": "1280:-2",
    "SD  (854)": "854:-2",
}

PRESETS = ["ultrafast", "superfast", "veryfast", "faster",
           "fast", "medium", "slow", "slower", "veryslow"]

AUDIO_OPTIONS = {
    "오디오 제거": "remove",
    "오디오 유지 (AAC 128k)": "aac_128",
    "오디오 유지 (AAC 192k)": "aac_192",
    "오디오 복사 (재인코딩 없음)": "copy",
}

FFMPEG_KNOWN = [
    str(APP_DIR / "ffmpeg" / "bin" / "ffmpeg.exe"),
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
]

# 컬러 테마
CLR_BG       = "#1e1e2e"
CLR_PANEL    = "#2a2a3e"
CLR_ACCENT   = "#7c6af7"
CLR_ACCENT2  = "#56d364"
CLR_TEXT     = "#cdd6f4"
CLR_SUBTEXT  = "#6c7086"
CLR_WARNING  = "#f38ba8"
CLR_BTN      = "#313244"
CLR_BTN_HOV  = "#45475a"
CLR_ENTRY    = "#313244"
CLR_PROGRESS = "#56d364"
CLR_HEADER   = "#11111b"


# ──────────────────────────────────────────────────────────────
#  유틸
# ──────────────────────────────────────────────────────────────

def find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for p in FFMPEG_KNOWN:
        if os.path.isfile(p):
            return p
    return None


def fmt_size(b: int) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"


def fmt_dur(s: float) -> str:
    return str(timedelta(seconds=int(s)))


def estimate_compression(codec: str, crf: int, src_size: int) -> tuple:
    """
    코덱와 CRF 설정에 기반한 예상 압축률 계산.
    소스 코덱이 H.264이면 H.265 전환으로 많이 줄어듦,
    이미 H.265면 소폭 줄어듦.
    Returns: (estimated_size_bytes, ratio_float)
    """
    c = codec.lower()
    if any(x in c for x in ("h264", "avc", "264")):
        base = 0.42   # H.264 → H.265: 약 42% 감소
    elif any(x in c for x in ("hevc", "h265", "265")):
        base = 0.15   # 이미 H.265: 약 15% 추가 감소
    elif any(x in c for x in ("mpeg4", "xvid", "divx", "mpeg-4")):
        base = 0.50   # 구형식 코덱: 약 50% 감소
    elif any(x in c for x in ("mjpeg", "prores", "dnxhd")):
        base = 0.75   # 로슬리스 코덱: 약 75% 감소
    elif any(x in c for x in ("wmv", "vc1")):
        base = 0.38
    else:
        base = 0.35   # 기타 (미상: H.264 유사)

    # CRF 28 기준, 1단위당 약 1.5% 추가 조정
    crf_adj = (crf - 28) * 0.015
    ratio = max(0.05, min(0.90, base + crf_adj))

    est_sz = int(src_size * (1 - ratio))
    return est_sz, ratio


def get_video_info(ffmpeg: str, path: str) -> dict:
    try:
        sz = os.path.getsize(path)
    except OSError:
        sz = 0

    info = {
        "duration": 0.0,
        "duration_str": "—",
        "resolution": "—",
        "codec": "—",
        "size": sz
    }
    try:
        # ffprobe 가 있으면 더 좋지만, ffmpeg -i 로 최대한 파싱
        r = subprocess.run(
            [ffmpeg, "-i", path],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        for line in r.stderr.splitlines():
            if "Duration:" in line:
                try:
                    d_str = line.split("Duration:")[1].split(",")[0].strip()
                    if d_str != "N/A":
                        info["duration_str"] = d_str.split(".")[0]  # ms 제거
                        h, m, s = d_str.split(":")
                        info["duration"] = int(h) * 3600 + int(m) * 60 + float(s)
                except Exception:
                    pass
            if "Video:" in line and "Stream" in line:
                try:
                    # resolution 추출 (예: 1920x1080)
                    import re
                    match = re.search(r" (\d{2,5}x\d{2,5})", line)
                    if match:
                        info["resolution"] = match.group(1)
                    
                    codec_part = line.split("Video:")[1].split(",")[0].strip()
                    info["codec"] = codec_part.split("(")[0].strip()
                except Exception:
                    pass
    except Exception:
        pass
    return info


def collect_videos(path: str, recursive: bool = False) -> list[str]:
    p = Path(path)
    result = []
    if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:
        return [str(p)]
    if p.is_dir():
        pattern = "**/*" if recursive else "*"
        for f in p.glob(pattern):
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                result.append(str(f))
    return sorted(result)


# ──────────────────────────────────────────────────────────────
#  압축 워커
# ──────────────────────────────────────────────────────────────

class CompressWorker:
    def __init__(self, ffmpeg, files, settings, out_queue):
        self.ffmpeg    = ffmpeg
        self.files     = files           # list of str
        self.settings  = settings
        self.q         = out_queue       # thread → GUI
        self._cancel   = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        total = len(self.files)
        done_size_in  = 0
        done_size_out = 0

        # files 리스트는 dict 형태: {path, name, display_name, rel_path, base_folder, ...}
        for idx, fobj in enumerate(self.files):
            if self._cancel.is_set():
                self.q.put(("cancelled", None))
                return

            src = fobj["path"]
            src_path = Path(src)
            rel_path  = fobj.get("rel_path", "")   # 하위 폴더 상대 경로 (없으면 "")
            display_name = fobj.get("display_name", src_path.name)
            self.q.put(("file_start", (idx, total, display_name)))

            # ── 출력 경로 결정 (폴더 구조 보존) ──
            if self.settings["out_mode"] == "comp":
                # 하위폴더 포함 모드: rel_path의 부모 경로를 Comp 안에 재현
                if rel_path:
                    rel_parent = Path(rel_path).parent
                    out_dir = src_path.parent
                    # rel_path 기준으로 루트 폴더를 역산하여 Comp 위치 결정
                    base_folder = fobj.get("base_folder", "")
                    if base_folder:
                        out_dir = Path(base_folder) / "Comp" / rel_parent
                    else:
                        out_dir = src_path.parent / "Comp"
                else:
                    out_dir = src_path.parent / "Comp"
            else:
                base_out = Path(self.settings["out_dir"])
                if rel_path:
                    rel_parent = Path(rel_path).parent
                    out_dir = base_out / rel_parent
                else:
                    out_dir = base_out
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / (src_path.stem + "_comp.mp4")

            # 이미 존재하면 덮어쓰기 (ffmpeg -y 로 처리)
            info = get_video_info(self.ffmpeg, src)

            # ── ffmpeg 명령 구성 ──
            cmd = [self.ffmpeg, "-y", "-loglevel", "error", "-i", src]

            resolution = self.settings["resolution"]
            if resolution:
                cmd += ["-vf", f"scale={resolution}:flags=lanczos"]

            cmd += [
                "-c:v", "libx265",
                "-crf", str(self.settings["crf"]),
                "-preset", self.settings["preset"],
                "-tag:v", "hvc1",
                "-map", "0:v:0",
            ]

            audio = self.settings["audio"]
            if audio == "remove":
                cmd.append("-an")
            elif audio == "copy":
                cmd += ["-map", "0:a?", "-c:a", "copy"]
            elif audio == "aac_128":
                cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "128k"]
            elif audio == "aac_192":
                cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]

            cmd += ["-progress", "pipe:1", "-nostats", str(out_path)]

            duration = info.get("duration", 0)
            start_t  = time.time()

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                last_lines = []
                while True:
                    if self._cancel.is_set():
                        proc.kill()
                        if out_path.exists():
                            out_path.unlink()
                        self.q.put(("cancelled", None))
                        return

                    line = proc.stdout.readline()
                    if not line and proc.poll() is not None:
                        break
                    line = line.strip()
                    if line:
                        last_lines.append(line)
                        if len(last_lines) > 20:
                            last_lines.pop(0)

                    if line.startswith("out_time_us="):
                        try:
                            us = int(line.split("=")[1])
                            if duration > 0:
                                pct = min(100.0, us / 1_000_000 / duration * 100)
                                elapsed = time.time() - start_t
                                eta = (elapsed / (pct / 100) - elapsed) if pct > 0 else 0
                                self.q.put(("file_progress", (pct, eta)))
                        except Exception:
                            pass

                proc.wait()
                in_sz  = os.path.getsize(src)
                out_sz = out_path.stat().st_size if out_path.exists() else 0

                if proc.returncode != 0 or out_sz == 0:
                    err_txt = "\n".join(last_lines)
                    self.q.put(("file_error", (src_path.name, err_txt[-300:])))
                    continue

                ratio    = (1 - out_sz / in_sz) * 100 if in_sz else 0
                elapsed  = time.time() - start_t
                done_size_in  += in_sz
                done_size_out += out_sz

                self.q.put(("file_done", {
                    "name":       src_path.name,
                    "display_name": display_name,
                    "in_sz":      in_sz,
                    "out_sz":     out_sz,
                    "ratio":      ratio,
                    "elapsed":    elapsed,
                    "out_path":   str(out_path),
                    "idx":        idx,
                }))

            except Exception as e:
                self.q.put(("file_error", (src_path.name, str(e))))

        overall_ratio = (1 - done_size_out / done_size_in * 100) if done_size_in else 0
        self.q.put(("all_done", {
            "total":     total,
            "in_total":  done_size_in,
            "out_total": done_size_out,
        }))


# ──────────────────────────────────────────────────────────────
#  GUI 클래스
# ──────────────────────────────────────────────────────────────

class VideoCompressorApp:
    def __init__(self, root: tk.Tk):
        self.root    = root
        self.ffmpeg  = find_ffmpeg()
        self.files   = []          # 대기열 {path, name, size, status}
        self.worker  = None
        self.wthread = None
        self.q       = queue.Queue()
        self._running = False
        
        # UI 변수 초기화
        self.recursive = tk.BooleanVar(value=False)
        self.del_orig = tk.BooleanVar(value=False)

        self._build_ui()
        self._set_icon()
        self._check_ffmpeg_startup()
        self.root.after(100, self._poll_queue)
    # ── 아이콘 설정 ──────────────────────────────────────
    def _set_icon(self):
        icon_path = APP_DIR / "assets" / "icons" / "app_icon.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

    # ── 툴바 구성 ────────────────────────────────────────
    def _build_toolbar(self, parent):
        tbar = tk.Frame(parent, bg=CLR_PANEL, height=45)
        tbar.pack(fill=tk.X, padx=8, pady=(0, 4))
        tbar.pack_propagate(False)

        btn_style = {
            "bg": CLR_PANEL, "fg": CLR_TEXT, "relief": tk.FLAT,
            "font": ("Malgun Gothic", 10), "padx": 12, "cursor": "hand2",
            "activebackground": CLR_BTN_HOV, "activeforeground": "white"
        }

        # 파일 열기
        tk.Button(tbar, text="📄 파일 추가 (복수)", **btn_style,
                  command=self._add_files).pack(side=tk.LEFT, fill=tk.Y)
        
        # 폴더 열기
        tk.Button(tbar, text="📁 폴더 열기", **btn_style,
                  command=self._add_folder).pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Frame(tbar, bg=CLR_BTN, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8, padx=10)

        # 저장 (출력 폴더)
        tk.Button(tbar, text="💾 저장 경로 설정", **btn_style,
                  command=self._browse_out).pack(side=tk.LEFT, fill=tk.Y)

        # 목록 비우기
        warn_style = btn_style.copy()
        warn_style["fg"] = CLR_WARNING
        tk.Button(tbar, text="🗑️ 목록 비우기", **warn_style,
                  command=self._clear_list).pack(side=tk.RIGHT, fill=tk.Y)

    # ── 메뉴 구성 ────────────────────────────────────────
    def _build_menu(self):
        menubar = tk.Menu(self.root)
        
        # 파일 메뉴
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="📄 파일 추가...", command=self._add_files, accelerator="Ctrl+O")
        file_menu.add_command(label="📁 폴더 추가...", command=self._add_folder, accelerator="Ctrl+D")
        file_menu.add_command(label="💾 저장 경로 설정(S)...", command=self._browse_out, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="🗑️ 목록 초기화", command=self._clear_list)
        file_menu.add_separator()
        file_menu.add_command(label="❌ 종료", command=self.root.quit, accelerator="Alt+F4")
        menubar.add_cascade(label="파일(F)", menu=file_menu)

        # 설정 메뉴
        opt_menu = tk.Menu(menubar, tearoff=0)
        opt_menu.add_checkbutton(label="하위 폴더 포함", variable=self.recursive)
        opt_menu.add_checkbutton(label="압축 후 원본 삭제", variable=self.del_orig)
        menubar.add_cascade(label="설정(S)", menu=opt_menu)
        
        # 도움말 메뉴
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="ffmpeg 확인", command=self._check_ffmpeg_manual)
        help_menu.add_separator()
        help_menu.add_command(label="프로그램 정보", command=self._show_about)
        menubar.add_cascade(label="도움말(H)", menu=help_menu)
        
        self.root.config(menu=menubar)
        
        # 단축키 바인딩
        self.root.bind_all("<Control-o>", lambda e: self._add_files())
        self.root.bind_all("<Control-d>", lambda e: self._add_folder())
        self.root.bind_all("<Control-s>", lambda e: self._browse_out())

    def _show_about(self):
        msg = f"{APP_TITLE}\n버전: {APP_VERSION}\n\n최신 H.265 코덱을 사용한 고효율 동영상 압축 도구입니다.\n© 2024 Video Compressor Pro"
        messagebox.showinfo("프로그램 정보", msg)

    # ── UI 구성 ──────────────────────────────────────────

    def _build_ui(self):
        r = self.root
        r.title(f"{APP_TITLE}  v{APP_VERSION}")
        r.geometry("1100x780")
        r.minsize(900, 640)
        r.configure(bg=CLR_BG)
        r.option_add("*Font", ("Malgun Gothic", 10))

        # ── 상단 타이틀 바 ──
        hdr = tk.Frame(r, bg=CLR_HEADER, height=50)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=APP_TITLE, bg=CLR_HEADER, fg=CLR_ACCENT,
                 font=("Malgun Gothic", 16, "bold")).pack(side=tk.LEFT, padx=16, pady=8)
        tk.Label(hdr, text=f"v{APP_VERSION}", bg=CLR_HEADER, fg=CLR_SUBTEXT,
                 font=("Malgun Gothic", 9)).pack(side=tk.LEFT, pady=14)

        self._build_toolbar(r)
        
        # ── 하단 영역 먼저 pack하여 창 크기에 밀려 사라지지 않게 함 ──
        btm_container = tk.Frame(r, bg=CLR_BG)
        btm_container.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_menu()

        btm = tk.Frame(btm_container, bg=CLR_BG)
        btm.pack(fill=tk.BOTH, padx=8, pady=4)
        
        self._build_progress(btm)
        self._build_log(btm)
        self._build_buttons(btm_container)

        # ── 메인 영역 (좌: 설정, 우: 파일 목록) ──
        main = tk.Frame(r, bg=CLR_BG)
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(2, 0))
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_settings(main)
        self._build_filelist(main)

    def _label(self, parent, text, **kw):
        return tk.Label(parent, text=text, bg=kw.pop("bg", CLR_PANEL),
                        fg=kw.pop("fg", CLR_TEXT), **kw)

    def _section(self, parent, title):
        f = tk.LabelFrame(parent, text=f"  {title}  ",
                          bg=CLR_PANEL, fg=CLR_ACCENT,
                          font=("Malgun Gothic", 9, "bold"),
                          bd=1, relief=tk.GROOVE, padx=8, pady=4)
        return f

    # ── 왼쪽 설정 패널 ──────────────────────────────────

    def _build_settings(self, parent):
        left = tk.Frame(parent, bg=CLR_PANEL, width=260, relief=tk.FLAT, bd=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.pack_propagate(False)

        pad = dict(padx=10, pady=3, sticky="ew")

        # ─ 해상도 ─
        sec1 = self._section(left, "📐 해상도")
        sec1.pack(fill=tk.X, padx=8, pady=(8, 4))
        self.res_var = tk.StringVar(value="FHD (1920)")
        cb_res = ttk.Combobox(sec1, textvariable=self.res_var,
                              values=list(RESOLUTIONS.keys()), state="readonly", width=22)
        cb_res.pack(fill=tk.X, pady=2)

        # ─ 품질 CRF ─
        sec2 = self._section(left, "🎯 품질 (CRF)")
        sec2.pack(fill=tk.X, padx=8, pady=4)
        crf_row = tk.Frame(sec2, bg=CLR_PANEL)
        crf_row.pack(fill=tk.X)
        self.crf_var = tk.IntVar(value=28)
        self.crf_lbl = tk.Label(crf_row, text="28", bg=CLR_PANEL, fg=CLR_ACCENT2,
                                font=("Consolas", 13, "bold"), width=3)
        self.crf_lbl.pack(side=tk.RIGHT)
        sc = ttk.Scale(crf_row, from_=18, to=40, variable=self.crf_var,
                       orient=tk.HORIZONTAL, command=self._on_crf)
        sc.pack(side=tk.LEFT, fill=tk.X, expand=True)
        row_hint = tk.Frame(sec2, bg=CLR_PANEL)
        row_hint.pack(fill=tk.X)
        tk.Label(row_hint, text="고품질(18)", bg=CLR_PANEL, fg=CLR_SUBTEXT,
                 font=("Malgun Gothic", 8)).pack(side=tk.LEFT)
        tk.Label(row_hint, text="최대압축(40)", bg=CLR_PANEL, fg=CLR_SUBTEXT,
                 font=("Malgun Gothic", 8)).pack(side=tk.RIGHT)

        # ─ 프리셋 ─
        sec3 = self._section(left, "⚡ 인코딩 속도")
        sec3.pack(fill=tk.X, padx=8, pady=4)
        self.preset_var = tk.StringVar(value="slow")
        cb_preset = ttk.Combobox(sec3, textvariable=self.preset_var,
                                 values=PRESETS, state="readonly", width=22)
        cb_preset.pack(fill=tk.X, pady=2)
        tk.Label(sec3, text="slow = 압축효율 우선 | fast = 속도 우선",
                 bg=CLR_PANEL, fg=CLR_SUBTEXT, font=("Malgun Gothic", 8)).pack()

        # ─ 오디오 ─
        sec4 = self._section(left, "🔊 오디오")
        sec4.pack(fill=tk.X, padx=8, pady=4)
        self.audio_var = tk.StringVar(value="오디오 제거")
        cb_audio = ttk.Combobox(sec4, textvariable=self.audio_var,
                                values=list(AUDIO_OPTIONS.keys()), state="readonly", width=22)
        cb_audio.pack(fill=tk.X, pady=2)

        # ─ 출력 경로 ─
        sec5 = self._section(left, "📁 출력 경로")
        sec5.pack(fill=tk.X, padx=8, pady=4)
        self.out_mode = tk.StringVar(value="comp")
        tk.Radiobutton(sec5, text="원본 폴더 내 'Comp' 서브폴더",
                       variable=self.out_mode, value="comp",
                       bg=CLR_PANEL, fg=CLR_TEXT, selectcolor=CLR_BTN,
                       command=self._on_out_mode).pack(anchor=tk.W)
        tk.Radiobutton(sec5, text="직접 폴더 지정",
                       variable=self.out_mode, value="custom",
                       bg=CLR_PANEL, fg=CLR_TEXT, selectcolor=CLR_BTN,
                       command=self._on_out_mode).pack(anchor=tk.W)
        self.out_dir_var = tk.StringVar(value="")
        self.out_dir_entry = tk.Entry(sec5, textvariable=self.out_dir_var,
                                      bg=CLR_ENTRY, fg=CLR_TEXT, state=tk.DISABLED,
                                      insertbackground=CLR_TEXT)
        self.out_dir_entry.pack(fill=tk.X, pady=(2, 0))
        self.btn_browse = tk.Button(sec5, text="📂 폴더 선택",
                                    bg=CLR_BTN, fg=CLR_TEXT, relief=tk.FLAT,
                                    state=tk.DISABLED, command=self._browse_out)
        self.btn_browse.pack(fill=tk.X, pady=(2, 0))

        # ─ 기타 옵션 ─
        sec6 = self._section(left, "⚙️ 기타 옵션")
        sec6.pack(fill=tk.X, padx=8, pady=4)
        tk.Checkbutton(sec6, text="폴더 추가 시 하위 폴더 포함",
                       variable=self.recursive,
                       bg=CLR_PANEL, fg=CLR_TEXT, selectcolor=CLR_BTN,
                       activebackground=CLR_PANEL).pack(anchor=tk.W)
        tk.Checkbutton(sec6, text="압축 후 원본 삭제",
                       variable=self.del_orig,
                       bg=CLR_PANEL, fg=CLR_TEXT, selectcolor=CLR_BTN,
                       activebackground=CLR_PANEL).pack(anchor=tk.W)

        # ─ 파일 추가 버튼 ─
        sec7 = self._section(left, "➕ 파일 추가")
        sec7.pack(fill=tk.X, padx=8, pady=(4, 8))
        tk.Button(sec7, text="📄 파일 열기",
                  bg=CLR_ACCENT, fg="white", relief=tk.FLAT,
                  font=("Malgun Gothic", 10, "bold"),
                  cursor="hand2", command=self._add_files).pack(fill=tk.X, pady=2)
        tk.Button(sec7, text="📁 폴더 열기",
                  bg=CLR_BTN, fg=CLR_TEXT, relief=tk.FLAT,
                  cursor="hand2", command=self._add_folder).pack(fill=tk.X, pady=2)
        tk.Button(sec7, text="🗑️  목록 초기화",
                  bg=CLR_BTN, fg=CLR_WARNING, relief=tk.FLAT,
                  cursor="hand2", command=self._clear_list).pack(fill=tk.X, pady=2)

    # ── 오른쪽 파일 목록 ─────────────────────────────────

    # ── 오른쪽 파일 목록 ─────────────────────────────────

    def _build_filelist(self, parent):
        right = tk.Frame(parent, bg=CLR_PANEL)
        right.grid(row=0, column=1, sticky="nsew")

        hdr = tk.Frame(right, bg=CLR_HEADER)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  📋 압축 대기열", bg=CLR_HEADER, fg=CLR_TEXT,
                 font=("Malgun Gothic", 10, "bold")).pack(side=tk.LEFT, pady=6)
        self.count_lbl = tk.Label(hdr, text="(0개)", bg=CLR_HEADER, fg=CLR_SUBTEXT,
                                  font=("Malgun Gothic", 9))
        self.count_lbl.pack(side=tk.LEFT, pady=6)

        cols    = ("name", "size", "estimated", "duration", "resolution", "status")
        col_hdr = ("파일명", "원본 크기", "예상 압축", "길이", "해상도", "상태")
        col_w   = (260, 75, 130, 65, 90, 110)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=CLR_PANEL, foreground=CLR_TEXT,
                        fieldbackground=CLR_PANEL, rowheight=24,
                        font=("Malgun Gothic", 9))
        style.configure("Treeview.Heading",
                        background=CLR_BTN, foreground=CLR_TEXT,
                        relief="flat", font=("Malgun Gothic", 9, "bold"))
        style.map("Treeview", background=[("selected", CLR_ACCENT)])

        frame_tree = tk.Frame(right, bg=CLR_PANEL)
        frame_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.tree = ttk.Treeview(frame_tree, columns=cols, show="headings", selectmode="extended")
        for c, h, w in zip(cols, col_hdr, col_w):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, minwidth=50)
        self.tree.tag_configure("done",    foreground=CLR_ACCENT2)
        self.tree.tag_configure("error",   foreground=CLR_WARNING)
        self.tree.tag_configure("running", foreground=CLR_ACCENT)
        self.tree.tag_configure("wait",    foreground=CLR_TEXT)

        vsb = ttk.Scrollbar(frame_tree, orient=tk.VERTICAL,   command=self.tree.yview)
        hsb = ttk.Scrollbar(frame_tree, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT,  fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.ctx_menu = tk.Menu(self.root, tearoff=0)
        self.ctx_menu.add_command(label="선택 항목 삭제", command=self._remove_selected)
        self.ctx_menu.add_command(label="출력 폴더 열기", command=self._open_out_dir)
        self.tree.bind("<Button-3>", self._show_ctx)




    # ── 진행률 ──────────────────────────────────────────────────────

    def _build_progress(self, parent):
        pf = tk.LabelFrame(parent, text="  📊 압축 진행률  ",
                           bg=CLR_PANEL, fg=CLR_ACCENT,
                           font=("Malgun Gothic", 9, "bold"),
                           bd=1, relief=tk.GROOVE)
        pf.pack(fill=tk.X, pady=(0, 4))

        style = ttk.Style()
        style.configure("file.Horizontal.TProgressbar",
                        troughcolor=CLR_BTN, background=CLR_ACCENT)
        style.configure("total.Horizontal.TProgressbar",
                        troughcolor=CLR_BTN, background=CLR_ACCENT2)

        # ─ 현재 파일 진행바 ─
        r1 = tk.Frame(pf, bg=CLR_PANEL)
        r1.pack(fill=tk.X, padx=10, pady=(8, 2))

        tk.Label(r1, text="현재 파일", bg=CLR_PANEL, fg=CLR_SUBTEXT,
                 font=("Malgun Gothic", 8), width=7, anchor=tk.W).pack(side=tk.LEFT)
        self.pb_file = ttk.Progressbar(r1, length=400, mode="determinate",
                                       style="file.Horizontal.TProgressbar")
        self.pb_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 6))
        self.lbl_file_pct = tk.Label(r1, text="0%", bg=CLR_PANEL, fg=CLR_ACCENT,
                                     font=("Consolas", 10, "bold"), width=5)
        self.lbl_file_pct.pack(side=tk.LEFT)

        # 파일명 + ETA
        r1b = tk.Frame(pf, bg=CLR_PANEL)
        r1b.pack(fill=tk.X, padx=10, pady=(0, 2))
        self.lbl_cur_file = tk.Label(r1b, text="대기 중...", bg=CLR_PANEL,
                                     fg=CLR_SUBTEXT, font=("Malgun Gothic", 8),
                                     anchor=tk.W)
        self.lbl_cur_file.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.lbl_elapsed = tk.Label(r1b, text="경과 —", bg=CLR_PANEL,
                                    fg=CLR_SUBTEXT, font=("Malgun Gothic", 8))
        self.lbl_elapsed.pack(side=tk.RIGHT, padx=12)
        self.lbl_eta = tk.Label(r1b, text="ETA —", bg=CLR_PANEL,
                                fg=CLR_SUBTEXT, font=("Malgun Gothic", 8))
        self.lbl_eta.pack(side=tk.RIGHT)

        # ─ 전체 진행바 ─
        r2 = tk.Frame(pf, bg=CLR_PANEL)
        r2.pack(fill=tk.X, padx=10, pady=(4, 2))

        tk.Label(r2, text="전체 진행", bg=CLR_PANEL, fg=CLR_SUBTEXT,
                 font=("Malgun Gothic", 8), width=7, anchor=tk.W).pack(side=tk.LEFT)
        self.pb_total = ttk.Progressbar(r2, length=400, mode="determinate",
                                        style="total.Horizontal.TProgressbar")
        self.pb_total.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 6))
        self.lbl_total_pct = tk.Label(r2, text="0%", bg=CLR_PANEL, fg=CLR_ACCENT2,
                                      font=("Consolas", 10, "bold"), width=5)
        self.lbl_total_pct.pack(side=tk.LEFT)

        # 파일 카운트 + 압축률
        r2b = tk.Frame(pf, bg=CLR_PANEL)
        r2b.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.lbl_total_cnt = tk.Label(r2b, text="0 / 0 파일", bg=CLR_PANEL,
                                      fg=CLR_SUBTEXT, font=("Malgun Gothic", 8),
                                      anchor=tk.W)
        self.lbl_total_cnt.pack(side=tk.LEFT)
        self.lbl_ratio = tk.Label(r2b, text="압축률 —", bg=CLR_PANEL,
                                  fg=CLR_ACCENT2, font=("Malgun Gothic", 8, "bold"))
        self.lbl_ratio.pack(side=tk.RIGHT)

    # ── 로그 ─────────────────────────────────────────────

    def _build_log(self, parent):
        lf = tk.Frame(parent, bg=CLR_PANEL)
        lf.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        hdr = tk.Frame(lf, bg=CLR_HEADER)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  📜 로그", bg=CLR_HEADER, fg=CLR_TEXT,
                 font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, pady=3)
        tk.Button(hdr, text="지우기", bg=CLR_BTN, fg=CLR_SUBTEXT,
                  relief=tk.FLAT, font=("Malgun Gothic", 8),
                  command=self._clear_log).pack(side=tk.RIGHT, padx=4)

        self.log_box = scrolledtext.ScrolledText(
            lf, height=6, bg=CLR_BG, fg=CLR_TEXT,
            font=("Consolas", 9), state=tk.DISABLED,
            insertbackground=CLR_TEXT, selectbackground=CLR_ACCENT,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.log_box.tag_configure("ok",   foreground=CLR_ACCENT2)
        self.log_box.tag_configure("err",  foreground=CLR_WARNING)
        self.log_box.tag_configure("info", foreground=CLR_ACCENT)
        self.log_box.tag_configure("dim",  foreground=CLR_SUBTEXT)

    # ── 하단 버튼 ─────────────────────────────────────────

    def _build_buttons(self, parent):
        bf = tk.Frame(parent, bg=CLR_HEADER)
        bf.pack(fill=tk.X, padx=8, pady=4)

        self.btn_start = tk.Button(
            bf, text="▶  압축 시작", bg=CLR_ACCENT, fg="white",
            font=("Malgun Gothic", 11, "bold"), relief=tk.FLAT,
            padx=20, cursor="hand2", command=self._start_compress)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 6), pady=4)

        self.btn_stop = tk.Button(
            bf, text="■  중지", bg=CLR_WARNING, fg="white",
            font=("Malgun Gothic", 11, "bold"), relief=tk.FLAT,
            padx=20, cursor="hand2", state=tk.DISABLED,
            command=self._stop_compress)
        self.btn_stop.pack(side=tk.LEFT, padx=6, pady=4)

        self.btn_cancel = tk.Button(
            bf, text="✖  취소", bg=CLR_BTN, fg=CLR_WARNING,
            font=("Malgun Gothic", 11, "bold"), relief=tk.FLAT,
            padx=20, cursor="hand2",
            command=self._clear_list)
        self.btn_cancel.pack(side=tk.LEFT, padx=6, pady=4)

        tk.Button(bf, text="🔍 ffmpeg 확인",
                  bg=CLR_BTN, fg=CLR_TEXT, relief=tk.FLAT,
                  padx=12, cursor="hand2", command=self._check_ffmpeg_manual).pack(
                  side=tk.LEFT, padx=6, pady=4)

        tk.Button(bf, text="❌ 종료",
                  bg=CLR_BTN, fg=CLR_WARNING, relief=tk.FLAT,
                  padx=12, cursor="hand2", command=self.root.quit).pack(
                  side=tk.RIGHT, padx=4, pady=4)

        self.status_lbl = tk.Label(bf, text="대기 중", bg=CLR_HEADER,
                                   fg=CLR_SUBTEXT, font=("Malgun Gothic", 9))
        self.status_lbl.pack(side=tk.LEFT, padx=20)

    # ── 이벤트 핸들러 ─────────────────────────────────────

    def _on_crf(self, val):
        self.crf_lbl.config(text=str(int(float(val))))
        self._update_estimates()

    def _update_estimates(self):
        """CRF 변경 시 대기 중인 모든 파일의 예상 압축률 업데이트"""
        crf = self.crf_var.get()
        for f in self.files:
            if f.get("status") == "wait":
                est_sz, ratio = estimate_compression(f.get("codec", ""), crf, f["size"])
                est_txt = f"~{fmt_size(est_sz)}  (-{ratio*100:.0f}%)"
                self.tree.item(f["iid"], values=(
                    f["display_name"], fmt_size(f["size"]), est_txt,
                    f.get("duration_str", "—"), f.get("resolution", "—"), "⏳ 대기"
                ))

    def _on_out_mode(self):
        mode = self.out_mode.get()
        state = tk.NORMAL if mode == "custom" else tk.DISABLED
        self.out_dir_entry.config(state=state)
        self.btn_browse.config(state=state)

    def _browse_out(self):
        d = filedialog.askdirectory(title="출력 폴더 선택")
        if d:
            self.out_dir_var.set(d)

    def _check_clear_before_add(self) -> bool:
        """
        작업이 끝난(완료/중지/취소/에러) 파일이 있으면 새 작업 시작 전 목록을 자동으로 비운다.
        - True : 진행
        - False: 취소
        """
        if not self.files:
            return True

        # 리스트에 하나라도 대기 상태만 있으면 그냥 추가 (작업 중복 베형)
        statuses = {f.get("status", "wait") for f in self.files}
        only_waiting = statuses <= {"wait"}
        if only_waiting and not self._running:
            return True

        # 대기 상태가 아닌 항목(완료, 에러 등)이 포함되어 있다면 목록을 초기화
        self.tree.delete(*self.tree.get_children())
        self.files.clear()
        self._refresh_count()
        self._log("이전 작업이 완료/중지되어 목록을 비우고 새 작업으로 시작합니다.", "info")
        
        # 진행바 및 UI 초기화
        self.pb_total["value"] = 0
        self.lbl_total_pct.config(text="0%")
        self.pb_file["value"] = 0
        self.lbl_file_pct.config(text="0%")
        self.lbl_eta.config(text="ETA —")
        self.lbl_elapsed.config(text="경과 —")
        self.lbl_cur_file.config(text="대기 중...")
        self.status_lbl.config(text="대기 중", fg=CLR_SUBTEXT)
        self.lbl_ratio.config(text="압축률 —")

        return True

    def _add_files(self):
        if self._running:
            messagebox.showwarning("경고", "압축 중에는 파일을 추가할 수 없습니다.")
            return
        if not self._check_clear_before_add():
            return

        paths = filedialog.askopenfilenames(
            title="영상 파일 선택",
            filetypes=[("영상 파일",
                        " ".join(f"*{e}" for e in sorted(VIDEO_EXTENSIONS))),
                       ("모든 파일", "*.*")]
        )
        if not paths:
            return
            
        added = 0
        for p in paths:
            if self._enqueue_file(p):
                added += 1
        if added:
            self._log(f"파일 {added}개 추가됨", "info")
            self._refresh_count()

    def _add_folder(self):
        if self._running:
            messagebox.showwarning("경고", "압축 중에는 폴더를 추가할 수 없습니다.")
            return
        if not self._check_clear_before_add():
            return

        folder = filedialog.askdirectory(title="폴더 선택")
        if not folder:
            return

        # ── 하위 폴더 포함 여부 다이얼로그 ──
        include_sub = messagebox.askyesno(
            "하위 폴더 포함",
            "하위 폴더의 영상 파일도 포함하시겠습니까?\n\n"
            "[예]  하위 폴더 포함 (폴더 구조 보존)\n"
            "[아니오]  현재 폴더만"
        )

        videos = collect_videos(folder, recursive=include_sub)
        added = 0
        base = Path(folder)
        for v in videos:
            # 상대 경로 계산 (하위 폴더 포함 시)
            try:
                rel = Path(v).relative_to(base)
            except ValueError:
                rel = Path(Path(v).name)
            rel_str = str(rel) if include_sub else ""
            if self._enqueue_file(v, base_folder=str(base), rel_path=rel_str):
                added += 1
        if added:
            mode_txt = "(하위 폴더 포함, 구조 보존)" if include_sub else ""
            self._log(f"폴더에서 {added}개 영상 추가됨: {folder} {mode_txt}", "info")
        else:
            self._log("추가할 영상이 없습니다.", "dim")
        self._refresh_count()

    def _enqueue_file(self, path: str, base_folder: str = "", rel_path: str = "") -> bool:
        # 중복 제거
        for f in self.files:
            if f["path"] == path:
                return False
        
        try:
            sz = os.path.getsize(path)
        except OSError:
            return False

        name = os.path.basename(path)
        display_name = rel_path if rel_path else name

        # 기본 정보 미리 채우기
        d_str, res, codec = "—", "—", ""
        if self.ffmpeg:
            info  = get_video_info(self.ffmpeg, path)
            d_str = info["duration_str"]
            res   = info["resolution"]
            codec = info.get("codec", "")

        # 예상 압축률 계산
        crf = self.crf_var.get()
        est_sz, ratio = estimate_compression(codec, crf, sz)
        est_txt = f"~{fmt_size(est_sz)}  (-{ratio*100:.0f}%)"

        iid = self.tree.insert("", tk.END,
                               values=(display_name, fmt_size(sz), est_txt, d_str, res, "⏳ 대기"),
                               tags=("wait",))

        self.files.append({
            "path":         path,
            "name":         name,
            "display_name": display_name,
            "rel_path":     rel_path,
            "base_folder":  base_folder,
            "size":         sz,
            "codec":        codec,
            "iid":          iid,
            "status":       "wait",
            "duration_str": d_str,
            "resolution":   res,
        })
        return True

    def _clear_list(self):
        if self._running:
            messagebox.showwarning("경고", "압축 중에는 목록을 초기화할 수 없습니다.")
            return
        self.tree.delete(*self.tree.get_children())
        self.files.clear()
        self._refresh_count()
        self._log("목록 초기화", "dim")

    def _remove_selected(self):
        if self._running:
            return
        selected = list(self.tree.selection())
        for iid in selected:
            self.tree.delete(iid)
        self.files = [f for f in self.files if f["iid"] not in selected]
        self._refresh_count()

    def _open_out_dir(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid  = sel[0]
        fobj = next((f for f in self.files if f["iid"] == iid), None)
        if not fobj:
            return
        if self.out_mode.get() == "comp":
            out = Path(fobj["path"]).parent / "Comp"
        else:
            out = Path(self.out_dir_var.get()) if self.out_dir_var.get() else Path(fobj["path"]).parent
        if out.exists():
            os.startfile(str(out))

    def _show_ctx(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.ctx_menu.post(event.x_root, event.y_root)

    def _refresh_count(self):
        n = len(self.files)
        total_sz = sum(f["size"] for f in self.files)
        self.count_lbl.config(text=f"({n}개 / {fmt_size(total_sz)})")

    # ── 압축 시작 / 중지 ─────────────────────────────────

    def _start_compress(self):
        if not self.ffmpeg:
            self._ask_install_ffmpeg()
            return
        if not self.files:
            messagebox.showinfo("알림", "파일을 먼저 추가하세요.")
            return
        if self.out_mode.get() == "custom" and not self.out_dir_var.get():
            messagebox.showwarning("경고", "출력 폴더를 선택하세요.")
            return

        settings = {
            "resolution":      RESOLUTIONS.get(self.res_var.get()),
            "crf":             int(self.crf_var.get()),
            "preset":          self.preset_var.get(),
            "audio":           AUDIO_OPTIONS.get(self.audio_var.get(), "remove"),
            "out_mode":        self.out_mode.get(),
            "out_dir":         self.out_dir_var.get(),
        }

        # 상태 초기화 (예상 압축 켼럼은 유지)
        for f in self.files:
            est_sz, ratio = estimate_compression(f.get("codec", ""), settings["crf"], f["size"])
            est_txt = f"~{fmt_size(est_sz)}  (-{ratio*100:.0f}%)"
            self.tree.item(f["iid"], values=(
                f["display_name"], fmt_size(f["size"]), est_txt,
                f.get("duration_str", "—"), f.get("resolution", "—"), "⏳ 대기"
            ), tags=("wait",))
        self.pb_total["value"] = 0
        self.pb_file["value"]  = 0

        self._running = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_lbl.config(text="압축 중...", fg=CLR_ACCENT)

        paths = self.files  # dict 리스트 그대로 전달 (rel_path, base_folder 포함)
        self.worker = CompressWorker(self.ffmpeg, self.files, settings, self.q)
        self.wthread = threading.Thread(target=self.worker.run, daemon=True)
        self.wthread.start()
        self._log("─" * 50, "dim")
        self._log(f"압축 시작  (CRF={settings['crf']}, preset={settings['preset']})", "info")

    def _stop_compress(self):
        if self.worker:
            self.worker.cancel()
        self.status_lbl.config(text="중지 요청...", fg=CLR_WARNING)

    # ── 큐 폴링 ──────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                msg, data = self.q.get_nowait()

                if msg == "file_start":
                    idx, total, display_name = data
                    self.pb_file["value"] = 0
                    self.lbl_file_pct.config(text="0%")
                    self.lbl_total_cnt.config(text=f"{idx} / {total} 파일")
                    self.lbl_cur_file.config(text=f"현재: {display_name[:60]}")
                    self.lbl_eta.config(text="ETA —")
                    self.lbl_elapsed.config(text="경과 —")
                    short = Path(display_name).name
                    self.status_lbl.config(text=f"처리 중: {short[:30]}")
                    for f in self.files:
                        if f["display_name"] == display_name:
                            self.tree.item(f["iid"], values=(
                                f["display_name"], fmt_size(f["size"]),
                                "🔄 압축 중", "—", "—", "🔄 압축 중"
                            ), tags=("running",))
                    self._log(f"▶ {display_name}", "info")

                elif msg == "file_progress":
                    pct, eta = data
                    self.pb_file["value"] = pct
                    self.lbl_file_pct.config(text=f"{pct:.0f}%")
                    self.lbl_eta.config(text=f"ETA {fmt_dur(eta)}" if eta > 0 else "ETA —")
                    # 경과 시간 결산
                    if pct > 0:
                        elapsed = eta * (pct / (100 - pct)) if pct < 100 else 0
                        self.lbl_elapsed.config(text=f"경과 {fmt_dur(elapsed)}")

                elif msg == "file_done":
                    d = data
                    done_cnt = sum(1 for f in self.files if f["status"] == "done") + 1
                    total    = len(self.files)
                    overall  = done_cnt / total * 100
                    self.pb_total["value"] = overall
                    self.lbl_total_pct.config(text=f"{overall:.0f}%")
                    self.lbl_total_cnt.config(text=f"{done_cnt} / {total} 파일")
                    self.pb_file["value"] = 100
                    self.lbl_file_pct.config(text="100%")
                    self.lbl_ratio.config(text=f"압축률 ↓{d['ratio']:.1f}%")
                    self.lbl_elapsed.config(text=f"경과 {fmt_dur(d['elapsed'])}")
                    self.lbl_eta.config(text="✔ 완료")
                    for f in self.files:
                        if f["display_name"] == d["display_name"]:
                            f["status"] = "done"
                            actual_txt = f"✅ {fmt_size(d['out_sz'])} (-{d['ratio']:.1f}%)"
                            self.tree.item(f["iid"], values=(
                                f["display_name"], fmt_size(d["in_sz"]),
                                actual_txt,
                                f.get("duration_str", "—"),
                                f.get("resolution", "—"),
                                "✅ 완료"
                            ), tags=("done",))
                    self._log(
                        f"  ✅ {d['display_name']}  "
                        f"{fmt_size(d['in_sz'])} → {fmt_size(d['out_sz'])}  "
                        f"({d['ratio']:.1f}%↓  {fmt_dur(d['elapsed'])})", "ok")

                elif msg == "file_error":
                    name, err = data
                    for f in self.files:
                        if f["name"] == name:
                            self.tree.item(f["iid"], values=(
                                f["display_name"], fmt_size(f["size"]),
                                "❌ 오류", "—", "—", "❌ 오류"
                            ), tags=("error",))
                    self._log(f"  ❌ {name}: {err}", "err")

                elif msg == "all_done":
                    d = data
                    ratio = (1 - d["out_total"] / d["in_total"]) * 100 if d["in_total"] else 0
                    self._running = False
                    self.btn_start.config(state=tk.NORMAL)
                    self.btn_stop.config(state=tk.DISABLED)
                    self.status_lbl.config(text="완료!", fg=CLR_ACCENT2)
                    self.pb_total["value"] = 100
                    self.lbl_total_pct.config(text="100%")
                    self._log("─" * 50, "dim")
                    self._log(
                        f"🎉 전체 완료!  "
                        f"{fmt_size(d['in_total'])} → {fmt_size(d['out_total'])}  "
                        f"({ratio:.1f}%↓)  총 {d['total']}개", "ok")

                    # 완료 요약 팝업
                    msg = (f"압축 완료!\n\n"
                           f"처리 파일: {d['total']}개\n"
                           f"원본 크기: {fmt_size(d['in_total'])}\n"
                           f"압축 크기: {fmt_size(d['out_total'])}\n"
                           f"절약 용량: {fmt_size(d['in_total'] - d['out_total'])}\n"
                           f"압축률:   {ratio:.1f}%")
                    messagebox.showinfo("완료", msg)

                    # 원본 삭제 의향 묻기
                    success_files = [f for f in self.files if f.get("status") == "done"]
                    if success_files:
                        if messagebox.askyesno("원본 삭제", "압축이 성공적으로 완료된 원본 파일들을 삭제하시겠습니까?"):
                            deleted = 0
                            for f in success_files:
                                try:
                                    if os.path.exists(f["path"]):
                                        os.remove(f["path"])
                                        deleted += 1
                                except Exception as e:
                                    self._log(f"삭제 실패: {f['name']} ({e})", "err")
                            if deleted > 0:
                                self._log(f"원본 파일 {deleted}개 삭제 완료.", "ok")
                                messagebox.showinfo("삭제 완료", f"원본 파일 {deleted}개가 삭제되었습니다.")

                elif msg == "cancelled":
                    self._running = False
                    self.btn_start.config(state=tk.NORMAL)
                    self.btn_stop.config(state=tk.DISABLED)
                    self.status_lbl.config(text="중지됨", fg=CLR_WARNING)
                    self._log("⚠️  사용자 중지", "err")

        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)

    # ── 로그 ─────────────────────────────────────────────

    def _log(self, msg: str, tag: str = ""):
        ts = time.strftime("%H:%M:%S")
        self.log_box.config(state=tk.NORMAL)
        self.log_box.insert(tk.END, f"[{ts}] ", "dim")
        self.log_box.insert(tk.END, msg + "\n", tag if tag else "")
        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete("1.0", tk.END)
        self.log_box.config(state=tk.DISABLED)

    # ── ffmpeg 확인 ──────────────────────────────────────

    def _check_ffmpeg_startup(self):
        if self.ffmpeg:
            self._log(f"ffmpeg 확인: {self.ffmpeg}", "ok")
        else:
            self._log("ffmpeg 를 찾을 수 없습니다. 설치가 필요합니다.", "err")
            # 팝업으로 다운로드 제안
            if messagebox.askyesno("ffmpeg 설치", "동영상 압축에 필요한 ffmpeg 엔진이 없습니다.\n지금 자동으로 다운로드하여 설치하시겠습니까?"):
                self._download_ffmpeg_gui()

    def _check_ffmpeg_manual(self):
        self.ffmpeg = find_ffmpeg()
        if self.ffmpeg:
            messagebox.showinfo("확인", f"ffmpeg 발견!\n{self.ffmpeg}")
        else:
            self._ask_install_ffmpeg()

    def _ask_install_ffmpeg(self):
        if messagebox.askyesno(
            "ffmpeg 없음",
            "ffmpeg 를 찾을 수 없습니다.\n"
            "자동으로 다운로드하시겠습니까? (약 80 MB)"
        ):
            self._download_ffmpeg_gui()

    def _download_ffmpeg_gui(self):
        win = tk.Toplevel(self.root)
        win.title("ffmpeg 다운로드")
        win.geometry("420x140")
        win.resizable(False, False)
        win.configure(bg=CLR_BG)
        win.grab_set()

        tk.Label(win, text="ffmpeg 다운로드 중...",
                 bg=CLR_BG, fg=CLR_TEXT,
                 font=("Malgun Gothic", 11)).pack(pady=(20, 6))
        lbl_status = tk.Label(win, text="준비 중...",
                              bg=CLR_BG, fg=CLR_SUBTEXT)
        lbl_status.pack()
        pb = ttk.Progressbar(win, mode="indeterminate", length=360)
        pb.pack(pady=10)
        pb.start(15)

        def _worker():
            try:
                from installer import check_and_install
                result = check_and_install(auto_download=True)
                self.ffmpeg = result.get("ffmpeg")
                msg = result.get("message", "")
                win.after(0, lambda: [pb.stop(), lbl_status.config(text=msg),
                                       win.after(2000, win.destroy)])
                if self.ffmpeg:
                    win.after(0, lambda: self._log(f"ffmpeg 설치 완료: {self.ffmpeg}", "ok"))
            except Exception as e:
                err_str = str(e)
                win.after(0, lambda: [pb.stop(), lbl_status.config(text=f"오류: {err_str}"),
                                       win.after(3000, win.destroy)])

        threading.Thread(target=_worker, daemon=True).start()


# ──────────────────────────────────────────────────────────────
#  진입점
# ──────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.configure(bg=CLR_BG)
    app = VideoCompressorApp(root)

    # 창 닫기 확인
    def on_close():
        if app._running:
            if messagebox.askyesno("종료", "압축 중입니다. 중지하고 종료하시겠습니까?"):
                if app.worker:
                    app.worker.cancel()
                root.destroy()
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
