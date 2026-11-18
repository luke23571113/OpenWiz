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
