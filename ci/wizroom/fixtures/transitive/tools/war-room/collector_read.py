from pathlib import Path

import sources

LIMITS = Path(__file__).resolve().parent / 'limits.conf'


def read():
    return sources.NAMES
