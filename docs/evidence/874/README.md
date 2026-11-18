# ER8 (#874) evidence

Fixture runs only; nothing here proves live behaviour.

## Red first (`d499a34`)

The release-build tests were changed to expect no engine, handover or activation
runtime before the runtimes were removed. Both failed because the collector still
required `tools/install/engine/engine.py` ("refused incomplete or non-native products"):

- [red-package.log](red-package.log): `Package.test_native_product_collector_checks_all_three_executable_architectures`
- [red-identity.log](red-identity.log): `test_product_identity.py`, 6 failures, all at the collector's return code

## Scoped checks at `6784411`

| Command | Result |
| --- | --- |
| `python3 -I tools/release/test_package.py` (real debug programs) | 6/6 pass |
| `python3 -I tools/release/test_product_identity.py` | 15/15 pass |
| `python3 tools/release/test.py` | 290/290 pass |
| `python3 -I tools/install/test_install.py` | pass |
| `python3 -I tools/install/access/test_access.py` | pass |
| `python3 -I tools/install/tests/journey/test_journey.py` | pass |
| Start-gate test with a fake gate-less `openwiz-service` (exits 0) | fails `0 != 1`, as it should |

## Helpers

None.
