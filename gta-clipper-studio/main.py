"""GTA CLIPPER STUDIO: rode com  python main.py  (ou dê dois cliques em Abrir GTA Clipper Studio.bat)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio.app import main  # noqa: E402

if __name__ == "__main__":
    main()
