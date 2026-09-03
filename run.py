from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from review_engine.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
