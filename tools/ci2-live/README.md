# CI2 live kits

**Kept (MT11, #830):** it tests the C11 main-batch observation kit: `test_batch_kit.py` refuses a kit missing a binding or holding a live command, `ci/main-batch/test_shadow.py` runs it in CI, and open #463 (CI2 C13) adds its acceptance kit here.

The kit is [batch-kit.md](batch-kit.md); `python3 -I tools/ci2-live/test_batch_kit.py` runs its offline checks.
