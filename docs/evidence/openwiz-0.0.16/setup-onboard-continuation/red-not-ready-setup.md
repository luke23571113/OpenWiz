# Red run: a not-ready setup invited the first idea (#636, CI follow-up)

The existing #2516 unit test, unchanged, at head 2ad4d5e (failed in CI's web-export job; reproduced locally with `node --test test/unit/first-hour-prerequisites.test.ts` in `apps/web`):

```text
✖ #2516: only current ready setup and fresh complete empty decisions with a successful no-fleet read invite the idea
  AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:
    actual: 'your turn'
    expected: 'waiting'
ℹ pass 12
ℹ fail 1
```

Cause: the connections step stopped reading setup's `ready` flag so that an unselected engine no longer blocks it, but that also counted a report saying not ready, with no unverified component to explain it, as done. Fix: only an unverified engine may explain a not-ready report; any other not-ready report stays unknown, and the first idea waits. The test is unchanged.

**After merging main for the real conflict with #919 (setup has no engine component since 0.0.17):** main's connections step shows any not-ready report as unknown ("Setup does not report ready yet."), which replaces this branch's engine-only rule. The merge keeps #636's two additions: an explicitly skipped App is excluded from the components that must be verified (the server's ready rule already excludes it), and the done line names the acting identity. The unchanged #2516 test passes on the merged tree (13 of 13).
