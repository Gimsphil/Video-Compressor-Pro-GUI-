"""
installer.py  ─  Video Compressor Pro 자동 의존성 설치
================================================================
실행하면:
  1) Python 버전 확인
  2) ffmpeg 탐색 (시스템 PATH + 알려진 경로 + 앱 로컬)
  3) ffmpeg 없으면 자동 다운로드 & 압축 해제
  4) 결과를 JSON 파일로 기록  → main.py 에서 읽음
================================================================
"""

import os
import sys
import json
import shutil
import zipfile
import urllib.request
import subprocess
from pathlib import Path

APP_DIR = Path(__file__).parent
ENV_FILE = APP_DIR / ".env.json"

# ── ffmpeg 다운로드 URL (gyan.dev Windows essentials build) ──
FFMPEG_ZIP_URL = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)
FFMPEG_LOCAL_DIR = APP_DIR / "ffmpeg"
FFMPEG_EXE       = FFMPEG_LOCAL_DIR / "bin" / "ffmpeg.exe"

# ── 알려진 ffmpeg 경로 (시스템 설치 가능성 있는 곳) ──
FFMPEG_KNOWN = [
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
]


# ──────────────────────────────────────────────────────────────
#  헬퍼
# ──────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"[installer] {msg}", flush=True)


def find_ffmpeg() -> str | None:
    """ffmpeg 실행 파일 경로 반환 (없으면 None)"""
    # 1) 로컬 앱 디렉토리
    if FFMPEG_EXE.exists():
        return str(FFMPEG_EXE)
    # 2) PATH
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 3) 알려진 경로
    for p in FFMPEG_KNOWN:
        if os.path.isfile(p):
            return p
    return None


def download_with_progress(url: str, dest: Path, label: str = "") -> None:
    """진행률 표시하며 파일 다운로드"""

    def reporthook(count, block_size, total_size):
        if total_size > 0:
            pct = min(100, count * block_size / total_size * 100)
            bar  = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
            print(f"\r  [{bar}] {pct:5.1f}%  {label}", end="", flush=True)

    log(f"다운로드 시작: {url}")
    urllib.request.urlretrieve(url, dest, reporthook)
    print()  # 줄바꿈


def extract_ffmpeg(zip_path: Path) -> bool:
    """ZIP 에서 ffmpeg.exe / ffprobe.exe 추출"""
    log("압축 해제 중...")
    FFMPEG_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    (FFMPEG_LOCAL_DIR / "bin").mkdir(exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            for name in names:
                base = os.path.basename(name)
                if base in ("ffmpeg.exe", "ffprobe.exe"):
                    target = FFMPEG_LOCAL_DIR / "bin" / base
                    with zf.open(name) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    log(f"  추출 완료: {base}")
        return FFMPEG_EXE.exists()
    except Exception as e:
        log(f"압축 해제 실패: {e}")
        return False


def install_ffmpeg() -> str | None:
    """ffmpeg 다운로드 → 설치 → 경로 반환"""
    zip_path = APP_DIR / "_ffmpeg_download.zip"
    
    # 이전에 중단된 파일이 있다면 삭제
    if zip_path.exists():
        try: zip_path.unlink()
        except: pass
        
    try:
        # User-Agent 추가로 거부 방지 및 타임아웃 설정
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        
        download_with_progress(FFMPEG_ZIP_URL, zip_path, "ffmpeg 다운로드")
        ok = extract_ffmpeg(zip_path)
        return str(FFMPEG_EXE) if ok else None
    except Exception as e:
        log(f"ffmpeg 설치 실패: {e}")
        return None
    finally:
        if zip_path.exists():
            try: zip_path.unlink()
            except: pass


# ──────────────────────────────────────────────────────────────
#  메인 체크 로직
# ──────────────────────────────────────────────────────────────

def check_and_install(auto_download: bool = True) -> dict:
    """
    모든 의존성 확인 후 결과 dict 반환
    {"ffmpeg": "<path>", "ok": True/False, "message": "..."}
    """
    result = {"ffmpeg": None, "ok": False, "message": ""}

    # Python 버전 확인
    if sys.version_info < (3, 8):
        result["message"] = f"Python 3.8 이상 필요 (현재: {sys.version.split()[0]})"
        return result

    log(f"Python {sys.version.split()[0]} ✓")

    # ffmpeg 탐색
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        log(f"ffmpeg 발견: {ffmpeg}")
        result.update({"ffmpeg": ffmpeg, "ok": True, "message": "모든 의존성 확인 완료"})
        save_env(result)
        return result

    log("ffmpeg 를 찾을 수 없습니다.")

    if not auto_download:
        result["message"] = "ffmpeg 없음 (수동 설치 필요)"
        return result

    log("ffmpeg 를 자동 다운로드합니다. (~80 MB)")
    ffmpeg = install_ffmpeg()

    if ffmpeg:
        log("ffmpeg 설치 완료 ✓")
        result.update({"ffmpeg": ffmpeg, "ok": True, "message": "ffmpeg 설치 완료"})
    else:
        result["message"] = "ffmpeg 설치 실패 — 수동으로 설치해주세요."

    save_env(result)
    return result


def save_env(data: dict) -> None:
    """환경 정보를 .env.json 에 저장"""
    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_env() -> dict:
    """저장된 환경 정보 로드"""
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ──────────────────────────────────────────────────────────────
#  직접 실행 시
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  Video Compressor Pro ─ 의존성 설치 도구")
    print("=" * 50)
    result = check_and_install(auto_download=True)
    if result["ok"]:
        print(f"\n✅ {result['message']}")
        print(f"   ffmpeg: {result['ffmpeg']}")
    else:
        print(f"\n❌ {result['message']}")
        sys.exit(1)
