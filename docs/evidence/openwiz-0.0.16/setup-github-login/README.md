# #633: setup's GitHub sign-in and explicit App skip: targets and red runs

Synthetic evidence for ticket #633 (spec #625, 0.0.16 T2). Every value here is
synthetic: the login `synthetic-owner` and the repository
`synthetic-owner/synthetic-consumer`. Nothing here is a live observation.

## Target pictures (design targets, made before the page changed)

| File | State | Width (CSS px) |
| --- | --- | --- |
| `target-skipped-desktop.png` | The owner skipped the App: Personal GitHub verified with an acting-identity note; the App row `missing`, reason "Skipped: …" | 1440 |
| `target-skipped-phone.png` | The same, single column | 390 |
| `target-offer-desktop.png` | Login verified, App missing: a note offers the explicit skip, naming the login that would act | 1440 |
| `target-offer-phone.png` | The same, single column | 390 |

- **Route:** OpenAI's built-in image tool in Codex (Sol 6.1, medium), no API key,
  with real screenshots of the current setup page as references. The exact
  prompts are in [prompts.md](prompts.md).
- **Post-processing:** the generated images came back wider than asked (about
  1487 and 720 px) and carried an embedded provenance metadata chunk. Each one
  was redrawn in headless Chromium at exactly its CSS width, which drops the
  metadata. The pixels are scaled only; the content is unchanged.
- **Known deviations from the reference:** slight gradients and differences in
  type, spacing and geometry that the generator kept despite a correction
  attempt. The targets fix the content, states and placement of the two
  changed rows; the real page keeps the existing design system, and the
  browser test's screenshots are what the page actually renders.
- **Approval:** a small change inside two existing rows, not a new screen or
  flow, so no owner approval of the picture is needed (image skill). The
  reviewer compares the real page with these targets.

## Red runs (each kept from the commit before its fix)

| Log | Proof | How it failed |
| --- | --- | --- |
| `red-store-py.log` | `test_github_login.py SavedIdentity` | Today's store refuses any `identity` field (`invalid setup state`) |
| `red-store-rs.log` | `setup::tests::identity_choice_reads_only_an_explicit_skip_or_nothing` | `SetupState` has no `identity` field (compile red: the shape is new) |
| `red-server.log` | the three new `setup::composed` tests | No `identity` in the report, the skipped App not `missing (skipped)`, no `identity_account_mismatch` code, and `ready` ignores the skip |
| `red-reader.log` | `tools/install/test_setup_api.mjs` | The page reader refuses a report carrying `identity` |
| `red-browser.log` | `apps/web/test/browser/setup-github-login.test.mjs` | The signed-out row has no browser sign-in guidance (first claim reached) |

Paths in the logs are reduced to `<checkout>` and `<tmp>`.

## Helpers

- Image generator (1): its slice was the four target pictures, at commit
  `7d4f16148075ddef11d51c5ef657a95b0fcb4458`. Result: ISSUES (width and style
  drift). Used: all four pictures, after redrawing them at exact widths. Found
  wrong: the dimensions. The helper made no repository change. No-push check:
  clean.
