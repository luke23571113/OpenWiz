import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'war-room'))
collector = importlib.import_module(name='collector')
print(collector.READ)
