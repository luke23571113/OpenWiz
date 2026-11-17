import os
from runpy import run_path as load

load(os.path.join(os.path.dirname(__file__), '..', 'war-room', 'runner.py'))
