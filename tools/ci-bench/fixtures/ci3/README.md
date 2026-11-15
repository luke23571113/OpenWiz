# CI3 synthetic window

`window.json` is synthetic (`openwiz.ci3-window.v1`): one day, 2026-01-05 UTC,
seven PR heads and one merge group. No value was observed on GitHub. Every
`ci` attempt has the same three jobs, so each number below can be checked by
hand. For an attempt created at `c` and ending at `e` (seconds after the head's
clock starts):

- `changes`: created `c`, runs `c+2` to `c+30`: set up 5 s and checkout 5 s
  (setup), the classifier 18 s (running);
- `rust`: created `c+30`, runs `c+33` to `e-20`: set up 3 s, `Rust 1.99.1` 40 s
  and complete 2 s (setup), `cargo test` the rest (running);
- `ci`: created `e-20`, runs `e-17` to `e`: set up 3 s (setup), and a step no
  row of `steps.tsv` names, 14 s (unclassified).

| PR | Head | `ci` | Result | Time |
| --- | --- | --- | --- | ---: |
| 101 | `a…` | `c=40`, `e=1200` | success | 1,200 s |
| 102 | `b…` | `c=20`, `e=2400` | failure | 2,400 s |
| 103 | `c…` | attempt 1 `c=20`, `e=600` failure; rerun `c=1800`, `e=2700` | success | 2,700 s |
| 104 | `d…` | `c=20`, `e=180`, cancelled by the next push | cancelled | 180 s |
| 105 | `e…` | `c=30`, `e=900` | success | 900 s |
| 106 | `f…` | still running when collected | missing: `ci: unfinished` | — |
| 107 | none | the push isn't in the activity | missing: `push time unknown` | — |

Each `privacy` run finishes before its `ci` run. Every job carries the attempt that ran it
(`run_attempt`), here always the attempt it is listed in.

**The measure:** five timed results, sorted 180, 900, 1200, 2400, 2700 s.
Nearest rank: p50 is the 3rd (1,200 s, **20.0 min**), p95 the 5th (2,700 s,
**45.0 min**). Counting only successful results, each timed from its last
attempt's first job (the bench's own cohort rule), would leave 870, 900 and
1,160 s: 15.0 and 19.3 min.

**Critical path** (`ci` ← `rust` ← `changes`, in the attempt that finished
last): setup is 10 + 45 + 3 = 58 s on every result; unclassified 14 s;
running is 18 s plus `cargo test`: 80, 790, 820, 1080, 2300 s (p50 820, p95
2300); the jobs on it hold a runner for `e − c − 8` s, and waiting is the rest:
28 (PR 104: 180 − 152), 28 (PR 102), 38 (PR 105), 48 (PR 101) and 1,808 s
(PR 103: 2,700 − 892, its failed attempt and the wait for the rerun included),
so p50 38 and p95 1,808.

**Runner minutes:** a `ci` attempt holds a runner for `e − c − 8` s and a
`privacy` run from 2 s after its creation to its end. PR heads: `ci` 1,152 +
2,372 + 572 + 892 + 152 + 862 = 6,002 s, `privacy` 258 + 178 + 228 + 128 + 368
+ 178 = 1,338 s, together 7,340 s = **122.3 min**. The merge group: `ci`
1,500 − 8 = 1,492 s and `privacy` 393 s = **31.4 min**, 25.0 min from its
first run to its last required check.
