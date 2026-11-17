import importlib.util
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location('suite', Path(__file__).with_name('suite.py'))
with open(os.path.join(os.path.dirname(__file__), 'data', 'rows.csv')) as f:
    print(f.read())
