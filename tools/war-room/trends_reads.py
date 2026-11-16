#!/usr/bin/env python3
"""The ci-bench trend code the war room reads with, moved here (#822, spec #819 revision 4).

Copied unchanged from tools/ci-bench/trends.py at its retirement's start: the
CF4 score reader, journey distributions, the outcome cohort and the journey
report check that a saved ci-benchmarks point carries. The journey module (J)
is the war room's own copy, moved from factory-metrics by MT2 (#821).
"""
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location('journey_for_bench', HERE/'journey.py')
J = importlib.util.module_from_spec(spec)
spec.loader.exec_module(J)
SCHEMA = 'closedwiz.journey.trends.v1'


def cf4_results(paths):
    """Read recorded CF4 scores only; never run or claim a paid eval."""
    results = []
    for path in paths:
        raw = Path(path).read_text()
        s = J.M.load(raw)
        keys = ('schema', 'settings_hash', 'cases_hash', 'revision', 'code_hash', 'schema_hash',
                'suite_pass', 'runs', 'passed', 'cost_usd', 'rows')
        J.M.exact(s, keys)
        J.require(s['schema'] == 'openwiz.skills-eval.score.v1', 'not a CF4 score')
        for k in ('settings_hash', 'cases_hash', 'code_hash', 'schema_hash'):
            J.require(type(s[k]) is str and J.re.fullmatch('[0-9a-f]{64}', s[k]), 'invalid CF4 hash')
        J.M.exact(s['revision'], ('commit', 'tree'))
        for v in s['revision'].values(): J.commit(v)
        J.require(type(s['suite_pass']) is bool, 'invalid CF4 outcome')
        J.count(s['runs'], 0); J.count(s['passed'], 0)
        J.require(s['passed'] <= s['runs'] and s['runs'] == len(J.array(s['rows'])), 'invalid CF4 counts')
        identities, repetitions = set(), {}
        for r in s['rows']:
            J.obj(r)
            required = ('case', 'repeat', 'pass', 'reasons', 'details')
            incomplete = set(r) == set(required)
            J.M.exact(r, required if incomplete else required + ('cost_usd', 'stop'))
            J.require(type(r['case']) is str and J.re.fullmatch('[a-z0-9][a-z0-9-]*', r['case']), 'invalid CF4 case')
            J.count(r['repeat'])
            key = (r['case'], r['repeat'])
            J.require(key not in identities, 'duplicate CF4 case/repeat')
            identities.add(key)
            repetitions.setdefault(r['case'], set()).add(r['repeat'])
            J.require(type(r['pass']) is bool, 'invalid CF4 row outcome')
            for k in ('reasons', 'details'):
                J.require(all(type(v) is str for v in J.array(r[k])), 'invalid CF4 reason/details')
            J.require(r['pass'] == (r['reasons'] == []), 'CF4 reasons disagree with outcome')
            if incomplete:
                J.require(not r['pass'] and r['reasons'] == ['incomplete'], 'invalid incomplete CF4 row')
            else:
                J.require(r['stop'] is None or type(r['stop']) is str, 'invalid CF4 stop')
                if r['cost_usd'] is not None: J.amount(r['cost_usd'])
                J.require(not r['pass'] or r['stop'] == 'end_turn', 'passing CF4 row did not finish')
        repeat_sets = list(repetitions.values())
        J.require(not repeat_sets or all(len(v) == len(repeat_sets[0]) and
                                        sorted(v) == list(range(1, len(v)+1)) for v in repeat_sets),
                  'CF4 cases have missing or inconsistent repeats')
        J.amount(s['cost_usd'])
        unfinished = any(r.get('stop') != 'end_turn' or 'incomplete' in r['reasons'] for r in s['rows'])
        J.require(sum(r.get('pass', False) for r in s['rows']) == s['passed'], 'CF4 pass count differs')
        J.require(s['suite_pass'] == bool(s['runs'] and s['passed'] == s['runs']), 'CF4 suite outcome disagrees')
        if s['suite_pass']:
            J.require(s['runs'] > 0 and s['passed'] == s['runs'] and not unfinished, 'inconsistent CF4 pass')
        results.append({'cf4': {k: s[k] for k in ('settings_hash', 'cases_hash', 'code_hash')} |
                        {'revision': s['revision']['commit']},
                        'schema_hash': s['schema_hash'], 'result_hash': hashlib.sha256(raw.encode()).hexdigest(),
                        'status': 'unfinished' if unfinished or not s['runs'] else 'passing' if s['suite_pass'] else 'failed'})
    return results


def histogram_summary(histogram, unknown=0):
    histogram = sorted(histogram.items())
    n = sum(count for _,count in histogram)
    mean = math.fsum(value*count for value,count in histogram)/n if n else None
    def rank(k):
        seen=0
        for value,count in histogram:
            seen+=count
            if seen>=k: return value
    median = ((rank((n+1)//2)+rank(n//2+1))/2) if n else None
    variance = math.fsum(count*(value-mean)**2 for value,count in histogram)/(n-1) if n>1 else None
    return {'n':n,'unknown':unknown,'mean':round(mean,6) if mean is not None else None,
            'median':round(median,6) if median is not None else None,
            'p90':round(rank(math.ceil(.9*n)),6) if n else None,
            'sample_sd':round(math.sqrt(variance),6) if variance is not None else None,
            'histogram':[{'value':v,'count':count} for v,count in histogram]}


def distribution(values, unknown=0):
    """Exact aggregate histogram; pooled quantiles never average daily medians."""
    return histogram_summary(Counter(values), unknown)


def outcome_cohort(doc, export, prs):
    rows = {r['pr']:r for r in J.outcome_rows(doc, export)}
    samples, starts, rounds = [], [], []
    g = dict.fromkeys(('mature','unmatured','unknown_followup','unknown_attribution',
                       'known_mature_prs','affected_mature_prs','attributable_events','unattributed_events'),0)
    for p in prs:
        r = rows[p['number']]
        if r['first_push_to_merged_hours'] is not None: samples.append(r['first_push_to_merged_hours'])
        if r['independent_rounds'] is not None: rounds.append(r['independent_rounds'])
        if r['builder_start_to_merged_hours'] is not None: starts.append(r['builder_start_to_merged_hours'])
        status = r['defect_followup']
        g['unknown_followup' if status == 'unknown' else status] += 1
        unknown = r['defects']['unknown'] > 0
        g['unknown_attribution'] += unknown
        g['attributable_events'] += r['defects']['attributable']
        g['unattributed_events'] += r['defects']['unattributed']
        if status == 'mature' and not unknown:
            g['known_mature_prs'] += 1
            g['affected_mature_prs'] += r['defects']['attributable'] > 0
    g['rate'] = round(g['affected_mature_prs']/g['known_mature_prs'],6) if g['known_mature_prs'] else None
    return {'prs':len(prs), 'first_push_to_merged_hours':distribution(samples,len(prs)-len(samples)),
            'builder_start_to_merged_hours':distribution(starts,len(prs)-len(starts)),
            'independent_rounds':distribution(rounds,len(prs)-len(rounds)), 'defects':g}


def validate_outcome_cohort(c):
    J.M.exact(c, ('prs','first_push_to_merged_hours','builder_start_to_merged_hours','independent_rounds','defects'))
    J.count(c['prs'],0)
    for key in ('first_push_to_merged_hours','builder_start_to_merged_hours','independent_rounds'):
        d = c[key]
        J.M.exact(d, ('n','unknown','mean','median','p90','sample_sd','histogram'))
        J.count(d['n'],0); J.count(d['unknown'],0)
        J.require(d['n']+d['unknown']==c['prs'], 'timing/round denominator differs')
        histogram={}; last=None
        for row in J.array(d['histogram']):
            J.M.exact(row, ('value','count')); J.amount(row['value']); J.count(row['count'])
            J.require(last is None or row['value']>last, 'unordered/repeated histogram value')
            last=row['value']
            histogram[float(row['value'])]=row['count']
        expected=histogram_summary(histogram,d['unknown'])
        J.require(json.loads(json.dumps(d,default=float))==expected, 'outcome statistics disagree with histogram')
    g=c['defects']
    J.M.exact(g, ('mature','unmatured','unknown_followup','unknown_attribution','known_mature_prs',
                  'affected_mature_prs','attributable_events','unattributed_events','rate'))
    for k in g:
        if k!='rate': J.count(g[k],0)
    J.require(g['mature']+g['unmatured']+g['unknown_followup']==c['prs'] and
              g['known_mature_prs']+g['unknown_attribution']<=c['prs'] and
              g['known_mature_prs']<=g['mature'] and
              g['affected_mature_prs']<=g['known_mature_prs'] and
              g['affected_mature_prs']<=g['attributable_events'], 'invalid defect denominators')
    J.require(g['rate']==(round(g['affected_mature_prs']/g['known_mature_prs'],6) if g['known_mature_prs'] else None),
              'defect rate differs from mature known denominator')


def validate_outcome_report(o):
    J.M.exact(o, ('all','merged','open','closed','tickets','defect_policy','assigned'))
    for key in ('all','merged','open','closed'): validate_outcome_cohort(o[key])
    J.require(o['merged']['prs']+o['open']['prs']+o['closed']['prs']<=o['all']['prs'],
              'outcome cohorts exceed collected PRs')
    t=o['tickets']; J.M.exact(t, ('total','merged','open','closed','without_pr'))
    for v in t.values(): J.count(v,0)
    J.require(t['total']==t['merged']+t['open']+t['closed'] and t['without_pr']<=t['total'], 'invalid ticket coverage')
    policy=o['defect_policy']
    if policy is not None:
        J.M.exact(policy, ('rule','followup_hours','deduplication','unknown_attribution'))
        J.require(policy['rule']=='explicit-causal-fix-link-v1' and policy['deduplication']=='root-cause-per-merge' and
                  policy['unknown_attribution']=='retain-unknown', 'unknown defect policy')
        J.amount(policy['followup_hours']); J.require(policy['followup_hours']>0, 'invalid follow-up')
    else:
        J.require(all(o[k]['defects']['unknown_followup']==o[k]['prs'] and
                      o[k]['defects']['attributable_events']==o[k]['defects']['unattributed_events']==0 and
                      o[k]['defects']['unknown_attribution']==0 for k in ('all','merged','open','closed')),
                  'defect comparison needs a policy')
    if o['assigned'] is not None:
        J.M.exact(o['assigned'], ('old','candidate'))
        for arm in o['assigned'].values():
            J.M.exact(arm, ('tickets','merged','open','closed','without_pr','outcomes'))
            for k in ('tickets','merged','open','closed','without_pr'): J.count(arm[k],0)
            J.require(arm['tickets']==arm['merged']+arm['open']+arm['closed'] and
                      arm['without_pr']<=arm['tickets'], 'invalid assignment coverage')
            validate_outcome_cohort(arm['outcomes'])


def validate(r):
    """Strict allowlist at the publication boundary; no raw journey fields."""
    J.M.exact(r, ('schema', 'since', 'until', 'cohorts', 'ready_to_merged_hours', 'findings',
                  'attributed_credits', 'daily_usage_ratios', 'experiments', 'coverage') +
                  (('outcomes',) if 'outcomes' in r else ()))
    if 'outcomes' in r:
        validate_outcome_report(r['outcomes'])
        J.require(r['outcomes']['merged']['prs']==r['cohorts']['merged']['prs'],
                  'outcome/legacy merged cohorts differ')
    J.require(r['schema'] == SCHEMA, 'unknown trend schema')
    J.require(J.M.timestamp(r['since']) < J.M.timestamp(r['until']), 'invalid trend window')
    def counts(d, keys):
        J.M.exact(d, keys)
        for v in d.values(): J.count(v, 0)
    def num(v):
        if v is not None: J.amount(v)
    J.M.exact(r['cohorts'], ('merged', 'reviewed', 'open'))
    for c in r['cohorts'].values():
        J.M.exact(c, ('prs', 'reviewed', 'unreviewed', 'first_approve', 'rounds', 'approval_share', 'rounds_per_pr'))
        for k in ('prs', 'reviewed', 'unreviewed', 'first_approve', 'rounds'): J.count(c[k], 0)
        J.require(c['prs'] == c['reviewed'] + c['unreviewed'] and c['first_approve'] <= c['reviewed'], 'invalid cohort counts')
        for k in ('approval_share', 'rounds_per_pr'): num(c[k])
        J.require(c['approval_share'] == (round(c['first_approve']/c['reviewed'], 6) if c['reviewed'] else None) and
                  c['rounds_per_pr'] == (round(c['rounds']/c['reviewed'], 6) if c['reviewed'] else None), 'invalid cohort ratios')
    t = r['ready_to_merged_hours']; J.M.exact(t, ('tickets', 'unknown', 'median', 'p90'))
    J.count(t['tickets'], 0); J.count(t['unknown'], 0); num(t['median']); num(t['p90'])
    counts(r['findings'], J.KINDS)
    J.M.exact(r['attributed_credits'], ('claude', 'gpt'))
    for c in r['attributed_credits'].values():
        J.M.exact(c, ('known_ticket_lower_bound', 'known_tickets', 'unknown_tickets', 'per_merged_pr'))
        J.count(c['known_tickets'], 0); J.count(c['unknown_tickets'], 0)
        num(c['known_ticket_lower_bound']); num(c['per_merged_pr'])
    for d in J.array(r['daily_usage_ratios']):
        J.M.exact(d, ('date', 'merged_prs', 'credits')); J.day(d['date']); J.count(d['merged_prs'], 0)
        J.M.exact(d['credits'], ('claude', 'gpt'))
        for u in d['credits'].values():
            J.M.exact(u, ('total', 'per_merged_pr')); num(u['total']); num(u['per_merged_pr'])
    for e in J.array(r['experiments']):
        J.M.exact(e, ('tag', 'revisions', 'merged_at', 'cf4', 'cf4_status', 'result_hash', 'schema_hash', 'baselines'))
        J.require(type(e['tag']) is str and J.TAG.fullmatch('Experiment: '+e['tag']), 'invalid experiment tag')
        J.M.exact(e['revisions'], ('base', 'head', 'merge'))
        for v in e['revisions'].values(): J.maybe_commit(v)
        J.when(e['merged_at'], null=True)
        if e['cf4'] is not None:
            J.M.exact(e['cf4'], ('settings_hash', 'cases_hash', 'code_hash', 'revision'))
            J.commit(e['cf4']['revision'])
            for k in ('settings_hash', 'cases_hash', 'code_hash'):
                J.require(type(e['cf4'][k]) is str and J.re.fullmatch('[0-9a-f]{64}', e['cf4'][k]), 'invalid CF4 hash')
        J.require(e['cf4_status'] in ('not recorded', 'passing', 'failed', 'unfinished'), 'invalid CF4 state')
        for k in ('result_hash', 'schema_hash'):
            J.require(e[k] is None or (type(e[k]) is str and J.re.fullmatch('[0-9a-f]{64}', e[k])), 'invalid result hash')
        J.require((e['cf4_status'] == 'not recorded') == (e['result_hash'] is None), 'CF4 state needs evidence')
        J.require(e['cf4_status'] == 'not recorded' or (e['cf4'] is not None and e['schema_hash'] is not None), 'CF4 outcome needs hashes')
        for s in J.array(e['baselines']):
            J.M.exact(s, ('cf4', 'schema_hash', 'result_hash', 'status'))
            J.M.exact(s['cf4'], ('settings_hash', 'cases_hash', 'code_hash', 'revision'))
            J.require(s['cf4']['revision'] == e['revisions']['base'], 'baseline must name base revision')
            J.commit(s['cf4']['revision'])
            for v in [s['schema_hash'], s['result_hash']] + [s['cf4'][k] for k in ('settings_hash', 'cases_hash', 'code_hash')]:
                J.require(type(v) is str and J.re.fullmatch('[0-9a-f]{64}', v), 'invalid baseline hash')
            J.require(s['status'] in ('passing', 'failed', 'unfinished'), 'invalid baseline outcome')
    c = r['coverage']
    J.M.exact(c, ('history', 'open_basis', 'selected_prs', 'merged_prs', 'unlinked_open_tickets',
                  'edited_events', 'unknown_events', 'duplicates_dropped'))
    J.require(c['history'] == 'unknown' and c['open_basis'] == 'current linked open PR snapshot; never a historical census', 'invalid coverage')
    for k in ('selected_prs', 'merged_prs', 'unlinked_open_tickets', 'edited_events', 'unknown_events', 'duplicates_dropped'):
        J.count(c[k], 0)
