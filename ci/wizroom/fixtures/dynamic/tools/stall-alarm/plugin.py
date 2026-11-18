import importlib.util
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('m', HERE.parent / 'war-room' / os.environ['SYNTHETIC_MODULE'])
