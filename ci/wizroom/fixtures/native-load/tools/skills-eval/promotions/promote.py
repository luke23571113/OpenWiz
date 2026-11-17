import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, path):
    location = Path(path)
    spec = importlib.util.spec_from_file_location(name, location)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


W = _load('promotion_weights', HERE.parents[1] / 'war-room' / 'weights.py')
