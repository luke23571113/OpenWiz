import os, signal, subprocess, sys, time
# Finite reproduction only: pause this runner, never unrelated processes.
p = subprocess.Popen(sys.argv[1:], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
try:
    end = time.monotonic() + 12
    pauses = 0
    while p.poll() is None and time.monotonic() < end:
        time.sleep(.020)
        if p.poll() is not None: break
        os.kill(p.pid, signal.SIGSTOP)
        time.sleep(.150)
        os.kill(p.pid, signal.SIGCONT)
        pauses += 1
    out, _ = p.communicate(timeout=40)
    print('pause load: runner stopped 150ms per 170ms; pauses:', pauses)
    print(out.decode(), end='')
    sys.exit(p.returncode)
finally:
    if p.poll() is None:
        os.kill(p.pid, signal.SIGCONT)
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
