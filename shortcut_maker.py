"""shortcut_maker.py - 바탕화면 바로가기 생성"""
import subprocess
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).parent.absolute()
PY_EXE  = sys.executable
MAIN_PY = str(APP_DIR / "main.py")
WORK    = str(APP_DIR)
DESKTOP = Path.home() / "Desktop"
LNK     = str(DESKTOP / "Video Compressor Pro.lnk")
ICON_PATH = str(APP_DIR / "assets" / "icons" / "app_icon.ico")

ps = """
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut(\"{lnk}\")
$sc.TargetPath       = \"{exe}\"
$sc.Arguments        = '\"{script}\"'
$sc.WorkingDirectory = \"{work}\"
$sc.Description      = \"Video Compressor Pro - H.265 Video Compression\"
$sc.IconLocation     = \"{icon}\"
$sc.Save()
Write-Host \"OK: {lnk}\"
""".format(
    lnk    = LNK,
    exe    = PY_EXE,
    script = MAIN_PY,
    work   = WORK,
    icon   = ICON_PATH,
)

ps_path = Path(os.environ.get("TEMP", r"C:\Temp")) / "make_lnk.ps1"
ps_path.write_text(ps, encoding="utf-8")

result = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_path)],
    capture_output=True, text=True,
)
if result.returncode == 0:
    print("바로가기 생성 완료:", LNK)
else:
    print("오류:", result.stderr[:300])

ps_path.unlink(missing_ok=True)
