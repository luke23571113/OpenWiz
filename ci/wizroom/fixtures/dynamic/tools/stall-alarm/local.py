import importlib.util
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('m', HERE / os.environ['SYNTHETIC_LOCAL'])
