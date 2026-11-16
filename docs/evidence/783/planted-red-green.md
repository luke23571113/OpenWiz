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
