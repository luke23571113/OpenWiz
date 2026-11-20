# Polish batch #1310, #1297, #1102, #1118: red runs

Synthetic runs only; the checkout path is replaced by `<checkout>`.

- `1310-red.log`: `sh ci/hosted/test.sh` at the base fake, with `ci/hosted/setup.sh`
  temporarily changed to write the source snapshot as
  `{ cat /etc/apt/sources.list.d/ubuntu.sources && echo; } > "$sources"`
  (one extra trailing newline). It prints `all ok`: the byte check missed it.
- `1310-mutant-after.log`: the same temporary mutation against the fixed fake.
  The byte check fails, as it should. The mutation is not committed.
- `1102-red.log`: `python3 -I ci/wizroom/test_split.py SplitChecker.test_javascript_regex_uncertainty_refuses_without_sets`
  before the fix: each of the four lexer refusals reads `native load`.
- `1118-red.log`: `python3 -I ci/wizroom/test_split.py SplitChecker.test_caller_supplied_sites_add_no_dependency_and_unlisted_loads_refuse`
  before the fix: a listed line's `os.environ.get` or `os.getenv` default moves (`{}` stay).
