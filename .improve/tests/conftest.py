"""The engine is a single module outside any package, so the tests put its directory on the path."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
