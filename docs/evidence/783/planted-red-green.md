# #783 planted case: local red/green

Commit `c443384` (the case row in `ci/select/planted.py`). The driver used planted.py's own `select` and `apply`, then ran only the picked browser tests (`node --test`), with the edit in place and then without it. The full lanes run in CI.

```text
case tools/install/setup/setup.py selection selected picked ['web:browser:install-access', 'web:browser:install-connections']
with-edit web:browser:install-access rc 0
with-edit web:browser:install-connections rc 1
without-edit web:browser:install-access rc 0
without-edit web:browser:install-connections rc 0
```

rc 1 with the edit: `install-connections` asserted each component `missing` but read `unknown`. Both pass without the edit.

## Verified selected CI failure

The replacement builder read the run metadata and both jobs directly through
GitHub's native Actions API. This reads existing evidence; no proof was rerun.

- [Proof PR #1050](https://github.com/openwizdev/OpenWiz/pull/1050), head
  `24f385db400836704d7b894906fffb73f5a4524f`, changes only
  `tools/install/setup/setup.py` (one addition and one deletion). Read-back:
  `state=CLOSED`, `mergedAt=null`.
- [Run 43973090712, attempt 1](https://github.com/openwizdev/OpenWiz/actions/runs/43973090712/attempts/1):
  `event=pull_request`, the same head, `conclusion=failure`.
- [Changes job 133670033141](https://github.com/openwizdev/OpenWiz/actions/runs/43973090712/job/133670033141):
  `CI selection: selected`; its web plan includes
  `web:browser:install-connections` (other selected tests also ran).
- [Web-export job 133670740222](https://github.com/openwizdev/OpenWiz/actions/runs/43973090712/job/133670740222):
  executes `test/browser/install-connections.test.mjs:164`; the assertion at
  line 183 fails. Actual states for `harness`, `personal_github`, `github_app`
  and `project` are `unknown`; expected states are `missing`.
- [Independent verification](https://github.com/openwizdev/OpenWiz/issues/783#issuecomment-6941059608)
  agrees. This is evidence of an actual selected test failure, not a failure
  from the draft gate, setup, or full-run fallback.

## Independent offline reproduction after merging main

At merge `c3b0a8060485e8c6db12617638dfcec73c3c1693` (parents: preserved
`665bd5389d7a321a0e1bc4ef3a69373c7af81800` and main
`894ab71f7c5517f641b3beb5d861da3c146d3035`), the replacement builder checked:

1. The planted row's replacement reproduces the entire single-file diff of
   `24f385db400836704d7b894906fffb73f5a4524f` byte-for-byte.
2. The committed measured map selects both direct readers,
   `web:browser:install-access` and `web:browser:install-connections`, in
   `selected` mode. Unknown/new tests may also be conservatively selected;
   these scoped checks run only the two direct readers, sequentially.
3. With the edit, `install-connections` exits 1 at its own line-183 assertion,
   with `ERR_ASSERTION`, `unknown` and `missing` in its output. The access test
   still exits 0. Both readers exit 0 after restoring the clean source.
4. `planted.verdict` reports the expected catcher and no hidden failure in
   this scoped set. The source is restored byte-for-byte even if a check fails.

Prerequisites: Rust 1.99.1, Node 24.22.1, Chromium, `npm ci --ignore-scripts`
and `CIRCLE_NODE_TOTAL=2 npm run build` in `apps/web`; build the fixture
server and CLI with `cargo build -p openwiz-tests --example openwiz-server
--bin fake-room-cli`. The first export build stopped after export with
Next.js's one-time security-upgrade notice; the same unmodified command then
exited 0. No dependency or product file was changed.

The independent driver, run from the repository root:

```sh
CARGO_BUILD_JOBS=2 python3 /tmp/783-verify-planted.py
```

Its complete assertion-bearing source (the temporary script is outside Git):

```python
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path.cwd();sys.path.insert(0,str(root/'ci/select'))
import planted,trace
case=next(c for c in planted.CASES if c[0]=='tools/install/setup/setup.py')
path,old,new,catchers=case
proof='24f385db400836704d7b894906fffb73f5a4524f'
changed=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',proof],text=True).splitlines()
assert changed==[path],changed
before=subprocess.check_output(['git','show',proof+'^:'+path]).decode()
after=subprocess.check_output(['git','show',proof+':'+path]).decode()
assert before.count(old)==1 and before.replace(old,new)==after
assert catchers==('web',)
mp=planted.pick.strict_json((root/'ci/select/map.json').read_text())
todo=trace.commands('web',str(root),2)
selection=planted.pick.select([('M',path)],mp,sorted(set(todo)|set(mp['units'])),lambda p:None,lambda ps:set())
readers=sorted(u for u,v in mp['units'].items() if path in v['files'])
assert readers==['web:browser:install-access','web:browser:install-connections'],readers
assert selection['mode']=='selected'
assert set(readers)<=set(selection['tests'])
print('head',subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),flush=True)
print('case',path,'exact throwaway edit confirmed; selection',selection['mode'],'direct readers',readers,flush=True)
original=(root/path).read_bytes(); results={}
try:
 planted.apply(str(root),path,old,new)
 for phase in ['with-edit','without-edit']:
  if phase=='without-edit':(root/path).write_bytes(original)
  for uid in readers:
   argv,cwd=todo[uid]
   log=Path('/tmp/783-'+phase+'-'+uid.split(':')[-1]+'.log')
   with log.open('w') as f: rc=subprocess.run(argv,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=240).returncode
   text=log.read_text();results[phase,uid]=rc
   print(phase,uid,'rc',rc,flush=True)
   if phase=='with-edit' and uid=='web:browser:install-connections':
    assert rc==1,(rc,text[-2000:])
    assert 'ERR_ASSERTION' in text and 'unknown' in text and 'missing' in text,text[-2000:]
    assert 'install-connections.test.mjs:183:' in text,text[-2000:]
   else: assert rc==0,(phase,uid,text[-3000:])
finally:
 (root/path).write_bytes(original)
assert (root/path).read_bytes()==original
v=planted.verdict(set(selection['tests'])&set(todo),{u:results['with-edit',u] for u in readers})
assert v=={'caught_by':['web:browser:install-connections'],'hidden':[]},v
print('planted verdict',json.dumps(v,sort_keys=True),flush=True)
print('source restored byte-for-byte sha256',hashlib.sha256(original).hexdigest(),flush=True)
print('PASS: exact edit caught; both selected direct readers pass clean; scoped proof only, full lanes remain CI',flush=True)
```

Observed output:

```text
head c3b0a8060485e8c6db12617638dfcec73c3c1693
case tools/install/setup/setup.py exact throwaway edit confirmed; selection selected direct readers ['web:browser:install-access', 'web:browser:install-connections']
with-edit web:browser:install-access rc 0
with-edit web:browser:install-connections rc 1
without-edit web:browser:install-access rc 0
without-edit web:browser:install-connections rc 0
planted verdict {"caught_by": ["web:browser:install-connections"], "hidden": []}
source restored byte-for-byte sha256 ffc603edbbea76edfee38185d679479c65b1ecc2155b5b7e46e04526a508578b
PASS: exact edit caught; both selected direct readers pass clean; scoped proof only, full lanes remain CI
```

The complete planted Rust/web lanes remain CI's responsibility; this local
result claims only the two direct-reader checks above. No live account,
installation, or external service behaviour is proved by these fixtures.

## Scope and supporting edits

Approval: spec #780 revision 3, fingerprint
`aa551ab4b6cc165ae8e7700022dc2908bb93fc7ef970800cc229b765882f68aa`
([approval](https://github.com/openwizdev/OpenWiz/issues/780#issuecomment-6934511268)).
The ready-proof exception is recorded on [#783](https://github.com/openwizdev/OpenWiz/issues/783#issuecomment-6904479822).
Option (b) remains dropped and unmerged; no workflow, signing, or C7 work is
included.

J110's standing supporting-edit rule in `docs/agents/fleet.md` covers:

- `docs/evidence/783/planted-red-green.md`, own evidence folder: supports
  CI3-S and the offline-case/README acceptance criteria by keeping the exact
  selected red CI evidence and independent offline red/green results.
- `tools/open-import/paths.json`, own shared-registry row only:
  `docs/evidence/783/**` allows that evidence to be carried. The main merge
  preserves every other ticket's rows unchanged.

The owned edits remain one `CASES` row in `ci/select/planted.py` and a new
proof section in `ci/select/README.md`. No file is added under `tools/ci-bench`.
This is infrastructure proof/evidence only, so no product changelog line is
needed (`no-changelog`). The existing new case catches mismatched setup
observation revisions; no extra unit test duplicates the browser assertion.

## Other scoped checks and known baseline failure

- `python3 -I ci/select/test_pick.py`: 48 tests, pass.
- `python3 -I ci/select/test_job.py`: 40 tests, pass (includes planted case
  shape, exact-once edit, catcher enforcement and hidden-failure checks).
- `python3 -I ci/select/test_trace.py`: 36 tests, pass.
- `cargo fmt --check`: pass.
- `cargo clippy --workspace --all-targets -- -D warnings`: pass (no Rust
  crate changed; the required hook independently runs this check).
- `python3 -I tools/open-import/test_guard.py`: 11 tests, pass.
- `python3 -I tools/open-import/test_frozen.py`: 15 tests, pass.
- `python3 -I tools/open-import/test_import.py`: 24 tests, 12 failures.
  Untouched main `894ab71f7c5517f641b3beb5d861da3c146d3035` reproduces the
  same 12 failures in a separate detached worktree. The fixtures still
  create two retired smoke paths, causing `unlisted source paths: 2` and
  `unlisted patch carriage`. This is already tracked as
  [needs-triage #921](https://github.com/openwizdev/OpenWiz/issues/921);
  #783 neither restores those paths nor changes the unrelated tests.

The replacement's first-push receipt is captured separately on the final PR.
The retired builder's original push timestamp is unavailable, not reconstructed.
