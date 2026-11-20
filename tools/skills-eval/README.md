# Skills eval

A behaviour eval of every shipped skill: synthetic cases, the real skill text, fake GitHub, CloudRoom and process tools, and a scorer for the agent's actions, their order and its records. Rules: [contract.md](contract.md). Python 3 standard library only.

```sh
python3 -I tools/skills-eval/test.py                  # offline proofs (free)
python3 -I tools/skills-eval/test_openrouter.py       # OpenRouter shape, cap and usage (free)
python3 -I tools/skills-eval/eval.py check            # every case valid, synthetic and covered (free)
python3 -I tools/skills-eval/eval.py coverage         # the skill-to-case map (free)
python3 -I tools/skills-eval/eval.py run --out DIR --env-file FILE   # paid runs, resumable
python3 -I tools/skills-eval/parallel.py --out DIR --env-file FILE   # the same set, four cases at once
python3 -I tools/skills-eval/eval.py score DIR        # exit 0 only if every case passed every repeat
python3 -I tools/skills-eval/eval.py compare A B      # refuses different settings or cases
python3 -I tools/skills-eval/eval.py tokens --results DIR --out FILE   # recorded provider usage (free)
python3 -I tools/skills-eval/eval.py tokens --offline --out FILE       # required-text bytes, not tokens
python3 -I tools/skills-eval/eval.py token-diff BEFORE AFTER
```

Paid runs need `OPENROUTER_API_KEY` from the environment or a dotenv file outside Git; without it they stop as not run. `settings.json` freezes the model, repeats, turn and token limits and the $20 total cap. Each request reserves its maximum cost first; an interrupted one keeps its reservation. One writer per results directory: never run `run` and `parallel.py` on one set at once. Token reports are DeepSeek's usage, not Claude tokens.

| File | What |
| --- | --- |
| `cases/`, `provenance.json` | One synthetic case per file; each case's source |
| `required-text.json` | The files one load of each skill requires |
| `settings.json` | The frozen run settings |
| `fakeworld.py` | The fake-tool boundary |
| `score.py`, `records.py`, `cases.py` | Scoring, record checks, case checks |
| `driver.py` | One paid role run |
| `tokens.py` | Required-text bytes and recorded token usage |
