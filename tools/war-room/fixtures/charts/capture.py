#!/usr/bin/env python3
"""WRD2 evidence: capture the synthetic chart figures in a real browser, network denied.

    python3 -I tools/war-room/fixtures/charts/capture.py OUT_DIR

Builds test_charts.full_world, writes OUT_DIR/charts (the build files), OUT_DIR/figures.html
(the figures section in the page's own head and CSP) and desktop.png / phone.png at
1440 and 390 CSS px wide. Writes only under OUT_DIR. Synthetic data only."""
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import test_charts as T  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='war-room-capture-') as tmp:
    d = Path(tmp)
    w, nat = T.full_world(d)
    b = T.build.build(w.history, at=T.BUILD_AT, source_root=w.root, selections=nat, out=out / 'charts')
    html = T.page.render(T.history.latest(w.history), charts=b)
    start = html.index('<section id="figures">'); end = html.index('</section>', start) + 10
    # The figures section alone, inside the page's own head (CSP and styles), for the capture.
    head = html[:html.index('<main>') + 6]
    (out / 'figures.html').write_text(head + html[start:end] + '</main></body></html>', encoding='utf-8')
    for name, width, height in (('desktop', 1440, 900), ('phone', 390, 844)):
        subprocess.run([T.publish.chromium(), '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
                        '--user-data-dir=' + str(d / name), '--host-resolver-rules=MAP * ~NOTFOUND', '--proxy-server=127.0.0.1:9',
                        '--window-size=%d,%d' % (width, 4200 if name == 'phone' else 2600), '--screenshot=' + str(out / (name + '.png')),
                        (out / 'figures.html').as_uri()], check=True, capture_output=True, timeout=90)
print(out)
