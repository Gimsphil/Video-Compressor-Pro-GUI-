"""
main.py  ─  Video Compressor Pro 진입점
"""
import sys
import os
import subprocess
from pathlib import Path

APP_DIR = Path(__file__).parent

# ── Python 3.14+ 감지 → subprocess로 3.13 재실행 ──
if sys.version_info >= (3, 14):
    py_base = Path(sys.executable).parent.parent  # .../Python314 → 상위
    CANDIDATES = [
        str(py_base / "Python313" / "python.exe"),
        str(py_base / "Python312" / "python.exe"),
        str(py_base / "Python311" / "python.exe"),
        r"C:\Python313\python.exe",
        r"C:\Python312\python.exe",
    ]
    py_stable = next((p for p in CANDIDATES if os.path.isfile(p)), None)

    if py_stable:
        # 3.13으로 재실행하고 현재 프로세스 종료
        ret = subprocess.call([py_stable, __file__] + sys.argv[1:])
        sys.exit(ret)
    else:
        sys.stdout.write("[오류] Python 3.13이 필요합니다. Python 3.14는 GUI를 지원하지 않습니다.\n")
        sys.stdout.write("설치: https://www.python.org/downloads/release/python-3130/\n")
        sys.stdout.flush()
        sys.exit(1)

# ── 정상 실행 (Python 3.13 이하) ──
sys.path.insert(0, str(APP_DIR))


def main():
    import installer

    env = installer.load_env()
    ffmpeg = env.get("ffmpeg")

    if not ffmpeg or not os.path.isfile(ffmpeg):
        ffmpeg = installer.find_ffmpeg()

    if not ffmpeg:
        if sys.stdin and sys.stdin.isatty():
            try:
                ans = input("ffmpeg 없음. 자동 다운로드? (y/n): ").strip().lower()
                if ans == "y":
                    installer.check_and_install(auto_download=True)
            except Exception:
                pass

    from video_compressor import main as run_gui
    run_gui()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        input("\n오류 발생. Enter를 눌러 종료...")
