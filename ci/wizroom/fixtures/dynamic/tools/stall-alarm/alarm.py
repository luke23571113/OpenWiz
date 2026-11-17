import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'war-room'))
reader = importlib.import_module(sys.argv[1])
