# CI3 loop: synthetic weeks

Everything here is synthetic: no value was observed on GitHub. The check reads
`now` = 2026-01-06T02:30:00Z, so its window is 2025-12-30T00:00:00Z to
2026-01-06T00:00:00Z (it ends on the hour, two hours before the read) and its
month is 2026-01.

- `github.json`: a fake GitHub, by path prefix (`{"$fail": ...}` is a failed
  read). One pull request, #9, and its two heads, as in `fixtures/ci3/`'s
  collect test: head 1 opened at 10:05:00 on the 10:00 push, done at 10:20:30
  (930 s); head 2 pushed at 11:00:00, `ci` red then rerun green at 11:42:00
  (2,520 s). Nearest rank over two results: p50 is the 1st, **15.5 min**, p95
  the 2nd, **42.0 min**. Its critical path: each result waits on its `ci` job
  alone (29 s and 119 s on a runner, no steps, so setup), so setup is
  148 s of 3,450 (4.3%), waiting 3,302 s (95.7%), running 0: **waiting** is the
  biggest bucket.
- Billing usage for 2026-01: Actions minutes 30,000 + 4,000.5 + 1,000 =
  35,000.5, read as **35,001** (rounded up, never under); the packages row is
  not Actions minutes.
- Spec #780's comments: a note by a record author (`synthetic-owner`) with
  p50 14.0 and p95 44.0, a plain comment, and a newer marker from someone who
  is not a record author, which is ignored. Against that note: p50 +1.5 min,
  p95 −2.0 min.
- `record.md`: a BEFORE record with p50 20.0 and p95 45.0: p50 −4.5 min and
  p95 −3.0 min, no regression.
