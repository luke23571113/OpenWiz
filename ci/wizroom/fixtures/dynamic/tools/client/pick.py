import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
collector = importlib.import_module('tools.war-room.' + sys.argv[1])
