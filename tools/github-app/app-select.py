#!/usr/bin/env python3
"""Red stub (#2661): today's pairing call, the token service on its default state."""
from pathlib import Path
import subprocess
import sys

done = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve().with_name("token-service.py")),
                       *sys.argv[1:]], stdin=sys.stdin, stdout=subprocess.PIPE, timeout=55)
sys.stdout.buffer.write(done.stdout)
sys.exit(done.returncode)
