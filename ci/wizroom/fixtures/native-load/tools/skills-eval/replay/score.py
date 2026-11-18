import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('score_contract', HERE.parents[1] / 'war-room/experiment_contract.py')
