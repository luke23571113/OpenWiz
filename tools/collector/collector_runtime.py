"""Shared current-run reader and privacy guards, extracted unchanged for WM2."""
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import activity
import sources

B = activity.B

TOKEN = re.compile(r'(?i)(?:\b(?:gh[pousr]_|github_pat_|sk-)[A-Za-z0-9_-]{8,}|authorization\s*:|bearer\s+'
                   r'|-----BEGIN .*PRIVATE KEY|\bthr_[A-Za-z0-9_-]+)')

def text_scan(text, checker):
    checker.text(text, 'published')
    if TOKEN.search(text):
        checker.findings += 1

LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"')

class Fail(Exception):
    pass

ACTIVE = ('in_progress', 'queued', 'waiting', 'pending', 'requested')

def current_runs(repo, since, until, read):
    """WR8's run reader, bounded: ci.yml's whole run history (over the API's 1000-item limit here)
    is listed as its active runs, one status at a time, and the completed runs created in
    [since, until], the only runs WR8's current_activity uses. Each listing keeps bench.pages'
    total_count and limit checks; a run listed twice, or under a status it does not have,
    refuses the read. The union is answered in WR8's page shape, newest first, one fresh
    listing per enumeration, so WR8's own before/after comparison still sees any change."""
    listed = 'repos/%s/actions/workflows/%s/runs?' % (repo, B.WORKFLOW)
    whole = re.compile(re.escape(listed + 'per_page=%d&page=' % B.PAGE) + r'([1-9][0-9]*)')
    union = []

    def listing():
        runs = {}
        queries = [('status=%s' % s, s) for s in ACTIVE] + [('created=%s..%s&status=completed' % (since, until), 'completed')]
        for query, status in queries:
            for value, where in B.pages(listed + query + '&per_page=%d' % B.PAGE, 'workflow_runs', 'runs', read):
                rid = B.as_int(B.as_obj(value, where), 'id', where)
                if rid in runs or B.as_str(value, 'status', where) != status:
                    raise B.Fail('current runs: a run listed twice or under another status')
                if status == 'completed' and not since <= B.as_time(value, 'created_at', where) <= until:
                    raise B.Fail('current runs: a completed run outside its created window')
                runs[rid] = value
        return [runs[r] for r in sorted(runs, reverse=True)]

    def answer(path):
        found = whole.fullmatch(path)
        if found is None:
            return read(path)
        page = int(found.group(1))
        if page == 1:
            union[:] = listing()
        return {'total_count': len(union), 'workflow_runs': union[(page - 1) * B.PAGE:page * B.PAGE]}
    return answer

def scan_bytes(data):
    """The existing privacy checker and credential/thread-id guard (publish.text_scan) over one artifact."""
    base = sources.native('tools/privacy-check/check.py')

    class Quiet(base.Checker):
        def refuse(self, *args, **kwargs):
            self.findings += 1
    checker = Quiet()
    try:
        text = data.decode('utf-8')
        text_scan(text, checker)
        # JSON escapes (\u0067, \/) hide a value from the bytes but not from a reader:
        # every JSON string literal, keys included, is scanned again as it decodes.
        text_scan('\n'.join(json.loads(s) for s in LITERAL.findall(text)), checker)
    except (UnicodeError, ValueError):
        raise Fail('the privacy scan refused a gathered binary or an undecodable string')
    if checker.findings:
        raise Fail('the privacy scan refused a gathered source')
