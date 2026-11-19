# FM2 proofs

The world, assignment manifest and daily export are synthetic. The GitHub
rows use the normal issue, PR, label, workflow and job response shapes.
Synthetic assumptions include a trusted push receipt arriving after the
PR opens, an edited claim and reviewer-start record, a duplicate verdict,
an outsider's imitation records, and a job relisted by a rerun.

The positive proof uses ticket 4101 in spec 4001. Claim to merge takes 2 h
30 min. It waited 15 min to be claimed, spent 85 min building, 18 min in
review, and 15 min in the merge queue. The jobs took 4 + 4 + 2 runner
minutes. One distinct independent verdict was recorded. The spec was open
for 3 h 15 min before the final merge.

The missing-source proof removes a job endpoint and withholds the private
assignments and usage. The GitHub timing and observed review still stand.
