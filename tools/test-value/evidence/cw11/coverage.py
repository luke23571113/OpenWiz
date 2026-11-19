"""Line coverage of CI's own Python modules under CI's own Python tests, with
the standard library's trace module (no dependency). Runs each test file in a
fresh interpreter from ROOT and sums executed lines per non-test module.
Scripts the tests start as subprocesses are not counted, on both sides alike."""
import json, os, subprocess, sys, tempfile, re, pathlib
root = pathlib.Path(sys.argv[1]).resolve(); out = sys.argv[2]
tests = sorted(p for p in subprocess.run(['git','-C',root,'ls-files','ci','.github/actions'],capture_output=True,text=True).stdout.split()
               if re.search(r'/test[^/]*\.py$', p) and not p.startswith('ci/wizroom/'))
runner = r'''
import sys, trace, runpy, os, pickle
test, data = sys.argv[1], sys.argv[2]
t = trace.Trace(count=1, trace=0, ignoredirs=[sys.prefix, sys.exec_prefix])
del sys.modules['trace']  # ci/select/trace.py shares the name
sys.argv = [test]
code = 0
try:
    t.runfunc(runpy.run_path, test, run_name='__main__')
except SystemExit as e:
    code = e.code or 0
counts = {}
for (f, l), n in t.results().counts.items():
    counts.setdefault(f, set()).add(l)
pickle.dump((code, counts), open(data, 'wb'))
'''
executed = {}; statuses = {}
for test in tests:
    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as tmp: pass
    r = subprocess.run([sys.executable, '-c', runner, test, tmp.name], cwd=root, capture_output=True, text=True, timeout=1200)
    import pickle
    try: code, counts = pickle.load(open(tmp.name,'rb'))
    except Exception: code, counts = 'unreadable', {}
    os.unlink(tmp.name)
    status = 'ok' if r.returncode == 0 and code == 0 else f'exit {r.returncode}/{code}'
    statuses[test] = status
    print(test, status, file=sys.stderr)
    for f, ls in counts.items():
        executed.setdefault(os.path.realpath(f), set()).update(ls)
import trace as _t
result = {}
for f, ls in executed.items():
    rel = os.path.relpath(f, root)
    if rel.startswith('..') or re.search(r'(^|/)test[^/]*\.py$', rel): continue
    lines = _t._find_executable_linenos(f)
    total = set(lines)
    result[rel] = dict(covered=len(total & ls), total=len(total), lines=sorted(total & ls))
json.dump(dict(tests=statuses, modules=dict(sorted(result.items()))), open(out,'w'), indent=1, sort_keys=True)
