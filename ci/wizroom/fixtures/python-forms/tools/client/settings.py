from pathlib import Path

print(Path(__file__).resolve().parent.parent.joinpath('war-room', 'settings.toml').read_text())
