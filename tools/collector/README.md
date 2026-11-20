# Public collector

The factory and CI readers used by OpenWiz's stall alarm, overload guard,
CI3, skills-eval and launch-fleet live here. The
[collector contract](collector.v1.md), schema identifiers and recorded units
are unchanged. `collector_runtime.py` shares the current-run reader and
privacy scan with the war room.

Offline checks:

```sh
python3 -I tools/collector/test_runtime.py
python3 -I tools/collector/test_collect_ci.py
python3 -I tools/collector/test_collect_factory.py
python3 -I tools/collector/ci3.py check-steps
```

The page, charts, site/history, publisher and serving adapter remain in
[`tools/war-room`](../war-room/) until WM3 imports them into private WizRoom.
The chart manifest, lockfile and chart code stay together there. The old
publisher entrypoints are unchanged; they import the public layer here.
See [spec #979](https://github.com/openwizdev/OpenWiz/issues/979).

## Weekly loop

CI3's loop runs every three days at 09:00 America/Los_Angeles. The
Cloudroom cron and `ci3_check.py due` gate preserve that Pacific schedule.
The portable [definition](../../loops/ci3-weekly.json) remains disabled and
in shadow; its fixed interval is not ready for takeover.

The definition computes occurrences as `anchor_ms + n * every_ms`, keeping
17:00 UTC: 09:00 Pacific in winter, but 10:00 during daylight saving time.
For example, occurrence 71 is 2027-06-17 at 17:00 UTC (10:00 Pacific),
whereas the Cloudroom schedule and gate use 16:00 UTC (09:00 Pacific).
A different constant anchor cannot preserve 09:00 in both seasons.

Before WizLoops takes over, a separately approved scheduling form must
preserve 09:00 America/Los_Angeles, with winter and summer parity checks
against Cloudroom. This is a takeover prerequisite, not permission to add
unsupported timezone or cron fields or to activate the definition.
