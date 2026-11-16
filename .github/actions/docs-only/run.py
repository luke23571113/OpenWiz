#!/usr/bin/env python3
"""Execute a persisted X5 plan, stamp successful lanes, and check actual needs.

No selection happens here. Prerequisites were computed by the changes job;
plan hashes prevent instructions or receipts from another plan being reused.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan as planner
import gate
sys.path.insert(0, str(HERE.parents[2] / 'ci/shard'))
import lanes

COMMANDS = {
    'release:ci2-read-contract': ['python3', '-I', 'tools/github-reads/test_contract.py'],
    'release:ci2-shared-reads': ['python3', '-I', 'tools/github-reads/test_read.py'],
    'release:ci2-read-consumers': ['python3', '-I', 'tools/github-reads/test_consumers.py'],
    'release:ci2-batch-shadow': ['python3', '-I', 'ci/main-batch/test_shadow.py'],
    'release:ci2-batch-contract': ['python3', '-I', 'ci/main-batch/test_contract.py'],
    'release:ci2-main-batch-admit': ['python3', '-I', 'ci/main-batch/test_admit.py'],
    'site:build': ['npm', 'run', 'build'], 'site:test': ['npm', 'test'],
    'site:ci': ['npm', 'run', 'test:ci'],
    'release:test': ['python3', 'tools/release/test.py'],
    'release:package': ['python3', '-I', 'tools/release/test_package.py'],
    'release:install': ['python3', '-I', 'tools/install/test_install.py'],
    'release:pull': ['python3', '-I', 'tools/install/test_pull.py'],
    'release:setup-api': ['node', '--test', 'tools/install/test_setup_api.mjs'],
    'release:github-app': ['python3', '-I', 'tools/github-app/test.py'],
    'release:security-baseline': ['python3', '-I', 'tools/install/tests/public-release-security/baseline/test_baseline.py'],
    'release:security-candidate': ['python3', '-I', 'tools/install/tests/public-release-security/test_candidate.py'],
    'release:open-tickets': ['sh', 'tools/open-tickets/test.sh'],
    'release:ci-runner': ['sh', '.github/actions/docs-only/test_rust_runner.sh'],
    'release:ci2-spending': ['python3', '-I', 'tools/ci-overflow/test.py', 'GuardedHosted'],
    'release:ops-live-controls': ['python3', '-I', 'tools/ops-live/controls/test_kit.py'],
    'release:ops-live-acceptance': ['python3', '-I', 'tools/ops-live/test_acceptance.py'],
    'release:ci2-overload': ['python3', '-I', 'tools/ci-overload/test.py'],
    'release:product-identity': ['python3', '-I', 'tools/release/test_product_identity.py'],
    'release:setup-onboard-contract': ['python3', '-I', 'tools/install/tests/setup-onboard-contract/test_contract.py'],
    'release:test-value': ['python3', '-I', 'tools/test-value/test_measure.py'],
    'release:test-value-unread-fixtures': ['python3', '-I', 'tools/test-value/test_unread_fixtures.py'],
    'release:setup-onboard-init': ['python3', '-I', 'tools/install/tests/init/test_init.py'],
    'release:setup-onboard-login': ['python3', '-I', '-B', 'tools/install/setup/test_github_login.py'],
    'release:setup-onboard-journey': ['python3', '-I', 'tools/install/tests/first-hour/test_first_merge.py'],
}
# This independent job cannot use the Rust job's target/.
# Its installed-engine proof consumes both debug binaries.
PACKAGE_BUILD = ['cargo','build','--locked','--jobs','2','-p','openwiz-cli','-p','openwiz-service','--bins']
# #743: the lanes CI splits across members (ci/shard/lanes.py), and the
# scripts among their units that split themselves by group and count cases.
SHARDED = {'release'} | {'skill:' + s for s in planner.skills.SHARDED}
COUNTED = {'skills/launch-fleet/scripts/test.sh'}


def load(folder):
    folder = Path(folder)
    record = gate.read_plan(folder / 'ci-selection.json')
    dispatch = gate.escapes.strict_json((folder / 'ci-dispatch.json').read_text())
    sha = hashlib.sha256((folder / 'ci-selection.json').read_bytes()).hexdigest()
    booleans = set(planner.steps.FLAGS) | {'rust','web','site','release','trace','planted','toolkit'}
    if (not isinstance(dispatch, dict) or set(dispatch) != booleans | {'skills','plan_sha256'}
            or dispatch['plan_sha256'] != sha
            or any(type(dispatch[k]) is not bool for k in booleans)):
        raise ValueError('missing, malformed or mismatched plan execution metadata')
    selected = [s['skill'] for s in record['lanes']['skills'] if s['decision']=='run']
    if dispatch['skills'] != selected:
        raise ValueError('skill execution metadata differs from plan')
    if record['selection']['mode']=='full' and not dispatch['toolkit']:
        raise ValueError('full plan requires the toolkit prerequisite')
    for key in ('rust','web'):
        if dispatch[key] != (record['lanes'][key]['decision']=='run'):
            raise ValueError(key + ' execution metadata differs from plan')
    for key in ('site','release'):
        if dispatch[key] != bool(tests_for(record,key)):
            raise ValueError(key + ' execution metadata differs from plan')
    export = record['builds']['web_export']['decision']=='run'
    if dispatch['build-web'] != export or any(dispatch[k] and not export for k in ('export-rust','export-web')):
        raise ValueError('export execution metadata differs from plan')
    for field, variable in (('id','GITHUB_RUN_ID'),('attempt','GITHUB_RUN_ATTEMPT'),('event','GITHUB_EVENT_NAME')):
        if os.environ.get(variable) != str(record['run'][field]):
            raise ValueError('plan does not belong to this run: ' + variable)
    return record, dispatch


def tests_for(record, kind):
    if kind=='build:web_export': return []
    if kind.startswith('skill:'):
        lanes = [s for s in record['lanes']['skills'] if s['skill']==kind[6:]]
        if len(lanes)!=1: raise ValueError('unknown skill lane: '+kind)
        return lanes[0].get('tests',[])
    lane = record['lanes']['site' if kind in ('site','release') else kind]
    tests = lane.get('tests',[])
    return [t for t in tests if t.startswith(kind+':')] if kind in ('site','release') else tests


def call(args, cwd=None, env=None):
    print('+ ' + ' '.join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True, env=env)


def units(record, kind):
    """A sharded lane's units in its run order: (id, [(command, cwd)...]).
    A COUNTED script's id is the lane's and its path; its groups are its units."""
    if kind.startswith('skill:'):
        return [(kind + ':' + c[-1], [(c, None)]) for c in planner.skills.SUITES[kind[6:]]]
    out = []
    if planner.combine_site_release(record):
        out.append(('site', [(COMMANDS[t], 'apps/site') for t in tests_for(record, 'site')]))
    for test in tests_for(record, kind):
        if test not in COMMANDS: raise ValueError('unknown planned test: '+test)
        if test == 'release:open-tickets':
            listed = subprocess.run([*COMMANDS[test], '--list'], check=True, capture_output=True, text=True).stdout.split()
            if not listed or len(set(listed)) != len(listed): raise ValueError('open-tickets lists no parts, or one twice')
            out += [(test + ':' + p, [([*COMMANDS[test], '--only', p], None)]) for p in listed]
        elif test == 'release:package':
            out.append((test, [(PACKAGE_BUILD, None), (COMMANDS[test], None)]))
        else:
            out.append((test, [(COMMANDS[test], None)]))
    return out


def counted(unit):
    return unit.split(':', 2)[-1] in COUNTED


def shares(record, kind, n, timed):
    """Every member's units: a COUNTED script's groups by its measured times."""
    ids = []
    for unit, _ in units(record, kind):
        ids += sorted((u for u in timed if u.startswith(unit + ':group:')), key=lambda u: int(u.rsplit(':', 1)[1])) \
            if counted(unit) else [unit]
    return lanes.split(ids, timed, n)


def execute_shard(folder, kind, spec, ran):
    """Member K of N (`execute PLAN KIND --shard K/N RAN`) runs its share of a
    sharded lane and records it in RAN, for the ci job's check-shards."""
    record, dispatch = load(folder)
    if kind not in SHARDED or (kind != 'release' and kind[6:] not in dispatch['skills']) \
            or (kind == 'release' and not dispatch['release']):
        raise ValueError('lane is not planned or not sharded: ' + kind)
    k, n = (int(x) for x in spec.split('/'))
    if not 1 <= k <= n: raise ValueError('bad shard ' + spec)
    timed = lanes.times()
    split, loads = shares(record, kind, n, timed)
    mine = set(split[k - 1])
    print(f'{kind} shard {k} of {n}: {len(mine)} units, about {loads[k - 1]:.0f} s', flush=True)
    done, counts = {}, {}
    for unit, commands in units(record, kind):
        if counted(unit):
            tmp = Path(os.environ['RUNNER_TEMP'])
            groups = {u.rsplit(':', 1)[1]: i for i, share in enumerate(split, 1) for u in share
                      if u.startswith(unit + ':group:')}
            (tmp / 'shard-map.txt').write_text(''.join(f'{g} {i}\n' for g, i in groups.items()))
            env = dict(os.environ, TEST_SHARD=spec, TEST_SHARD_MAP=str(tmp / 'shard-map.txt'),
                       TEST_SHARD_RAN=str(tmp / 'shard-ran.txt'))
            for command, cwd in commands: call(command, cwd, env)
            fields = {}
            for line in (tmp / 'shard-ran.txt').read_text().splitlines():
                key, *rest = line.split()
                if key == 'group': done[f'{unit}:group:{rest[0]}'] = int(rest[1]) / 1000
                else: fields[key] = int(rest[0])
            counts[unit] = {'cases': fields['cases'], 'total': fields['total'], 'groups': fields['groups']}
        elif unit in mine:
            start = time.monotonic()
            for command, cwd in commands: call(command, cwd)
            done[unit] = round(time.monotonic() - start, 2)
            print(f'== lane unit: {unit} {done[unit]:.0f} s', flush=True)
    Path(ran).parent.mkdir(parents=True, exist_ok=True)
    Path(ran).write_text(json.dumps(lanes.record(kind, k, n, dispatch['plan_sha256'], done, counts)))


def check_shards(folder, kind, *ran):
    """The ci job: every unit of a sharded lane ran exactly once, counts add up."""
    record, dispatch = load(folder)
    expected = [u for u, _ in units(record, kind) if not counted(u)]
    problems = lanes.check(kind, dispatch['plan_sha256'], expected,
                           [gate.escapes.strict_json(Path(p).read_text()) for p in ran])
    if problems: raise ValueError('shard check failed:\n' + '\n'.join(problems))


def trace(kind, selected, dispatch, full=False):
    if not dispatch['trace']: return False
    if subprocess.run(['python3','-I','ci/select/trace.py','ready']).returncode: return False
    if kind=='rust' and subprocess.run(['sh','ci/rust-tests.sh','--can-run-at-once']).returncode: return False
    if kind=='rust':
        args = ['cargo','test','--workspace','--no-run','--locked'] if selected!=['rust:test:checks'] else ['cargo','test','-p','openwiz-tests','--test','checks','--no-run','--locked']
        call(args)
    args = ['python3','-I','ci/select/trace.py',kind,os.path.join(os.environ['RUNNER_TEMP'],'select-records'),'--jobs','3']
    if selected and not (kind=='web' and full): args += ['--only',*selected]
    code = subprocess.run(args).returncode
    if code==3:
        print('trace: tracer failed; run selected tests normally and make no map',flush=True)
        shutil.rmtree(os.path.join(os.environ['RUNNER_TEMP'],'select-records'),ignore_errors=True)
        return False
    if code: raise subprocess.CalledProcessError(code,args)
    return True


def execute(folder, kind):
    record, dispatch = load(folder)
    tests = tests_for(record,kind)
    if kind == 'release' and planner.combine_site_release(record):
        execute(folder, 'site')
    if kind=='build:web_export':
        if record['builds']['web_export']['decision']!='run': raise ValueError('export is not planned')
        if not trace('export',[],dispatch): call(['npm','run','build'],cwd='apps/web')
        call(['npm','run','typecheck'],cwd='apps/web')
        call(['npm','run','check'],cwd='apps/web')
    elif kind=='rust' and not tests and dispatch['toolkit']:
        print('Rust route owns only the planned toolkit prerequisite')
    elif not tests:
        raise ValueError('lane is not planned: '+kind)
    elif kind=='always':
        call(['cargo','fmt','--check'])
        call(['sh','.github/actions/docs-only/test.sh','--always'])
        call(['sh','ci/hosted/test.sh'])
        for script in ('test_pick.py','test_trace.py','test_job.py','test_steps.py'):
            call(['python3','-I','ci/select/'+script])
        if not trace('rust',['rust:test:checks'],dispatch):
            call(['cargo','test','-p','openwiz-tests','--test','checks','--locked'])
    elif kind=='rust':
        # Selected tests can execute debug binaries even when lint was skipped.
        # Prepare them before tracing, its fallbacks, and planted tests alike.
        call(['cargo','build','--workspace','--bins','--locked'])
        if not trace('rust',tests,dispatch): call(['sh','ci/rust-tests.sh','--only',' '.join(tests)])
        if dispatch['planted']:
            call(['python3','-I','ci/select/planted.py','rust',os.path.join(os.environ['RUNNER_TEMP'],'select-records/planted-rust.jsonl'),'--jobs','3'])
    elif kind=='web':
        full = record['selection']['mode']=='full'
        if not trace('web',tests,dispatch,full=full):
            if full:
                call(['npm','test'],cwd='apps/web')
            else:
                paths = planner.units.web_units('.')
                call(['node','test/run-browser.mjs','--with-unit','--only',*[paths[t] for t in tests]],cwd='apps/web')
        if dispatch['planted']:
            call(['python3','-I','ci/select/planted.py','web',os.path.join(os.environ['RUNNER_TEMP'],'select-records/planted-web.jsonl'),'--jobs','3'])
    elif kind.startswith('skill:'):
        # Each matrix member executes exactly its named suite. A missing or
        # invalid plan is an error, never skills.py's permissive all fallback.
        for command in planner.skills.SUITES[kind[6:]]: call(command)
    else:
        for test in tests:
            if test not in COMMANDS: raise ValueError('unknown planned test: '+test)
            if test=='release:package':
                call(PACKAGE_BUILD)
            call(COMMANDS[test],cwd='apps/site' if test.startswith('site:') else None)


def lint(folder):
    record, dispatch = load(folder)
    if dispatch['lint-rust']:
        call(['cargo','clippy','--workspace','--all-targets','--','-D','warnings'])
        call(['cargo','build','--workspace','--locked'])
        call(['cargo','build','--release','--locked'])
    else: print('Rust build and lint: no changed Rust input')


def lint_always(folder):
    _,dispatch=load(folder)
    if not dispatch['rust'] and not dispatch['toolkit']:
        lint(folder)
    else:
        print('Rust test lane owns the requested lint/build work')


def receipt(record, dispatch, kind, tests):
    return dict(lane=kind,tests=tests,plan_sha256=dispatch['plan_sha256'],run=record['run'])


def toolkit(folder, outcome, receipts):
    record,dispatch=load(folder)
    if not dispatch['toolkit']:
        if outcome not in ('','skipped'):
            raise ValueError('unplanned toolkit outcome: '+repr(outcome))
        return
    if outcome!='success':
        raise ValueError('toolkit prerequisite expected success, got '+repr(outcome))
    receipts=Path(receipts);receipts.mkdir(parents=True,exist_ok=True)
    (receipts/'prerequisite-toolkit.json').write_text(json.dumps(
        receipt(record,dispatch,'prerequisite:toolkit',[])))


def stamp(folder, kind, receipts):
    record, dispatch = load(folder)
    tests = tests_for(record,kind)
    if kind=='rust' and dispatch['toolkit']:
        path=Path(receipts)/'prerequisite-toolkit.json'
        expected=receipt(record,dispatch,'prerequisite:toolkit',[])
        if not path.is_file() or json.dumps(gate.escapes.strict_json(path.read_text()),sort_keys=True)!=json.dumps(expected,sort_keys=True):
            raise ValueError('missing or mismatched toolkit prerequisite receipt')
        if not tests:
            return
    if not tests and kind!='build:web_export': raise ValueError('cannot stamp unplanned lane '+kind)
    if kind=='build:web_export' and record['builds']['web_export']['decision']!='run':
        raise ValueError('cannot stamp unplanned export')
    receipts = Path(receipts); receipts.mkdir(parents=True,exist_ok=True)
    (receipts/(kind.replace(':','-')+'.json')).write_text(json.dumps(receipt(record,dispatch,kind,tests)))
    if kind == 'release' and planner.combine_site_release(record):
        stamp(folder, 'site', receipts)


def finish(folder, needs_path, receipts):
    record, dispatch = load(folder)
    needs = gate.escapes.strict_json(Path(needs_path).read_text())
    if not isinstance(needs,dict): raise ValueError('needs must be an object')
    def result(job, active):
        entry = needs.get(job,{})
        if not isinstance(entry,dict): raise ValueError(job+': unreadable job result')
        state = entry.get('result')
        if active and state!='success': raise ValueError(job+': expected success, got '+repr(state))
        if not active and state not in (None,'skipped'): raise ValueError(job+': expected skipped, got '+repr(state))
        return state
    outcomes = {k: result(k,True) for k in ('changes','always')}
    outcomes['build:web_export'] = result('web-build',dispatch['build-web'])
    for kind in ('rust','web'):
        exported = dispatch['export-'+kind]
        state=result(kind+'-export' if exported else kind,dispatch[kind] or (kind=='rust' and dispatch['toolkit']))
        outcomes[kind] = state if dispatch[kind] else 'skipped'
        result(kind if exported else kind+'-export',False)
    result('site', dispatch['site'] and not planner.combine_site_release(record))
    result('release', dispatch['release'])
    outcomes['site'] = 'success' if dispatch['site'] or dispatch['release'] else 'skipped'
    sharded = [s for s in dispatch['skills'] if s in planner.skills.SHARDED]
    result('skills',len(dispatch['skills'])>len(sharded))
    for skill in planner.skills.SHARDED: result(skill,skill in sharded)
    expected = {k: tests_for(record,k) for k in ('always','rust','web','site','release') if tests_for(record,k)}
    expected.update({'skill:'+s: tests_for(record,'skill:'+s) for s in dispatch['skills']})
    if dispatch['build-web']: expected['build:web_export']=[]
    if dispatch['toolkit']: expected['prerequisite:toolkit']=[]
    seen = set()
    for path in sorted(Path(receipts).glob('*.json')):
        entry = gate.escapes.strict_json(path.read_text())
        if not isinstance(entry,dict) or set(entry)!={'lane','tests','plan_sha256','run'}:
            raise ValueError('malformed receipt '+path.name)
        name = entry['lane']
        if not isinstance(name,str) or name not in expected or name in seen:
            raise ValueError('unexpected or duplicate receipt '+repr(name))
        if (entry['plan_sha256']!=dispatch['plan_sha256'] or not isinstance(entry['tests'],list)
                or sorted(entry['tests'])!=sorted(expected[name])
                or json.dumps(entry['run'],sort_keys=True)!=json.dumps(record['run'],sort_keys=True)):
            raise ValueError(name+': receipt does not bind the exact plan and tests')
        seen.add(name)
    missing = set(expected)-seen
    if missing: raise ValueError('missing lane receipts: '+', '.join(sorted(missing)))
    outcomes.update({'skill:'+s: 'success' for s in dispatch['skills']})
    gate.check(record,outcomes,os.environ)
    print('ci: every planned lane passed')


if __name__=='__main__':
    try:
        mode,*args=sys.argv[1:]
        if mode=='execute' and len(args)==5 and args[2]=='--shard': execute_shard(args[0],args[1],args[3],args[4])
        elif mode=='execute': execute(*args)
        elif mode=='check-shards': check_shards(*args)
        elif mode=='lint': lint(*args)
        elif mode=='lint-always': lint_always(*args)
        elif mode=='stamp': stamp(*args)
        elif mode=='toolkit': toolkit(*args)
        elif mode=='finish': finish(*args)
        else: raise ValueError('unknown plan runner command')
    except Exception as error:
        print('ci: '+str(error),file=sys.stderr)
        sys.exit(1)
