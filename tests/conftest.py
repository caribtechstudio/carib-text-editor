"""Rend les modules de Carib importables depuis les tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
