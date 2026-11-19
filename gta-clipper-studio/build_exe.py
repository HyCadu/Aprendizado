"""Gera o executável  gta-clipper-studio\\GTA Clipper Studio.exe  (um arquivo só, sem janela de console).

Uso (na pasta Aprendizado):  python gta-clipper-studio\\build_exe.py
Precisa de:  pip install pyinstaller PySide6

O .exe precisa ficar dentro da pasta do projeto (ou indique o projeto na variável GTA_CLIPPER_REPO),
porque ele usa as skills de .claude/skills. O processamento continua usando o Python e o Claude Code instalados.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

NAME = "GTA Clipper Studio"
EXCLUDES = ["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
            "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DExtras", "PySide6.QtCharts",
            "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
            "PySide6.QtDesigner", "PySide6.QtQuick3D", "PySide6.QtSql", "PySide6.QtTest"]


def make_icon(path: Path):
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841
    from studio.app import app_icon
    pm = app_icon().pixmap(256, 256)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not pm.save(str(path), "ICO"):
        raise SystemExit("não consegui gerar o ícone")


def main():
    ico = HERE / "build" / "app.ico"
    make_icon(ico)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
           "--name", NAME, "--icon", str(ico), "--distpath", str(HERE), "--workpath", str(HERE / "build"),
           "--specpath", str(HERE / "build"), "--paths", str(HERE)]
    for m in EXCLUDES:
        cmd += ["--exclude-module", m]
    cmd.append(str(HERE / "main.py"))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(r.returncode)
    exe = HERE / f"{NAME}.exe"
    print(f"\nPronto: {exe}  ({exe.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
