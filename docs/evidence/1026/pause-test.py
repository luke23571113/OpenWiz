"""Finite #763-style descheduling probe; only the test process is signalled."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import tempfile

program = Path(sys.argv[1]).resolve()
checkout = Path(__file__).resolve().parents[3]
# The first durable claim is shared by the old and corrected keeper.
start = time.time()
p = subprocess.Popen([str(program), '--exact',
    'ad_send_attachments::ad07_every_row_of_the_outcome_table', '--nocapture'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
try:
    until = time.monotonic() + 10
    while p.poll() is None:
        # The core assigns its deadline before claiming the send.
        records = list((Path(tempfile.gettempdir()) / 'openwiz-messaging-tests').glob(
            f'{p.pid}-*/ad07_outcomes-state/sends/op-ad07-sent.json'))
        if records:
            os.kill(p.pid, signal.SIGSTOP)
            time.sleep(2.2)
            os.kill(p.pid, signal.SIGCONT)
            print('pause load: stopped this runner for 2.2s after first durable send record')
            break
        if time.monotonic() >= until:
            raise RuntimeError('durable send record not observed')
        time.sleep(.001)
    out, _ = p.communicate(timeout=20)
    print(out.decode(), end='')
    sys.exit(p.returncode)
finally:
    if p.poll() is None:
        os.kill(p.pid, signal.SIGCONT)
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
