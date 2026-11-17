"""Run one synthetic interleaving probe; reject setup or assertion mismatches."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('test_binary', type=Path)
p.add_argument('expect', choices=['red', 'green'])
a = p.parse_args()
root = Path(__file__).resolve().parent
is_gate = root.name == '946'
source = root / ('reservation-race.c' if is_gate else 'recovery-launch.c')
test = ('aw05_gate::a_forged_send_with_an_attachment_that_is_not_ready_is_refused_with_zero_calls'
        if is_gate else 'e11_plan_bounds::e11_plan_deadline_retains_its_slot_until_the_source_really_finishes')
with tempfile.TemporaryDirectory(prefix='openwiz-flake-probe-') as tmp:
    lib = Path(tmp) / 'probe.so'
    subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                    str(source), '-ldl', '-pthread', '-o', str(lib)], check=True)
    result = subprocess.run([str(a.test_binary.resolve()), '--exact', test, '--nocapture'],
        env={**os.environ, 'LD_PRELOAD': str(lib)}, capture_output=True, text=True, timeout=45)
    text = result.stdout + result.stderr
    print(text, end='')
    assert 'running 1 test' in text, 'proof was not selected'
    marker = ('probe: holding aborted-upload cleanup' if is_gate else 'probe: fourth plan launch descheduled')
    assert marker in text, 'interleaving probe never fired'
    if a.expect == 'red':
        assert result.returncode == 101 and '0 passed; 1 failed' in text, 'expected assertion red'
        if is_gate:
            assert 'store_unavailable' in text and 'attach_support.rs' in text, 'wrong red'
            assert 'removed between scan read and directory listing' in text, 'scan race not observed'
        else:
            assert 'left: 504' in text and 'right: 200' in text, 'wrong red'
    else:
        assert result.returncode == 0 and '1 passed; 0 failed' in text, 'expected pass'
    print('probe outcome matched:', a.expect)
