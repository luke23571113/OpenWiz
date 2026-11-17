import json, pathlib, sys, unittest
sys.path.insert(0, 'tools/install/setup')
import test_github_login as t
original = t.os.utime
def measure(path, times):
    record = json.loads(pathlib.Path(path).read_text())
    marker = pathlib.Path(path).parents[2] / 'gh/auth.pid'
    child = int(marker.read_text())
    print(f'Before ageing pending record: durable pid={record["pid"]}, living child={child}', flush=True)
    assert record['pid'] == child, 'test killed wrapper before child PID was durably recorded'
    return original(path, times)
t.os.utime = measure
unittest.main(module=t, argv=['measure', 'SignIn.test_a_restart_while_approval_is_pending_starts_no_second_browser'], verbosity=2)
