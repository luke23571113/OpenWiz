# War room page assets (WRD3, #631)

Everything here is embedded in the page's own HTML. The page makes no request for
it, and nothing here is executed.

| File | What | Rights |
| --- | --- | --- |
| `citadel.css` | The masthead engraving, drawn in CSS gradients and one `clip-path` | Written for this repository; same licence as the repository |
| `oswald-bold-latin.woff2` | Oswald Bold, Basic Latin subset, for page headings only | SIL Open Font License 1.1, [`OFL.txt`](OFL.txt) |
| `OFL.txt` | The font's licence and copyright notice, unchanged from upstream | — |

## Oswald Bold: source, version and hash chain

Approval: Jake, 2026-11-15, J85. Oswald 4.103 Bold only, a Basic Latin WOFF2
subset, page headings only, embedded as data. The page CSP gains only
`font-src data:`. Public record:
[#631 comment 6899209435](https://github.com/openwizdev/OpenWiz/issues/631#issuecomment-6899209435).
This is page-asset provenance. It adds no package to `dependencies.md`, the
lockfile or any runtime.

| Step | Value |
| --- | --- |
| Upstream | `googlefonts/OswaldFont`, commit `89795261ac9eeb9aa8cd99f43982c4e4b0e53261` (2024-05-29, `main`) |
| Source file | `fonts/ttf/Oswald-Bold.ttf`, 108,496 bytes, git blob `4314b91e6d54f2404a5f54415c7eb98d74d3d6a0` |
| Source SHA-256 | `eb7d46f856dd57f18a8c03d033c57802692bf127f01dbd95ba8984338e6b5135` |
| Source metadata | name ID 1 `Oswald`, ID 2 `Bold`, ID 5 `Version 4.103; ttfautohint (v1.8.4.7-5d5b);gftools[0.9.33.dev8+g029e19f]`; `head.fontRevision` 4.103; `OS/2.usWeightClass` 700 |
| Licence | `OFL.txt` from the same commit, SHA-256 `0fd731a904b729a4e02eaf5e8ebd06783edd9abe400e8882760160230675b652`; the font's name ID 0 and 13 carry the copyright and OFL notice |
| Subset recipe | fontTools 4.55.3 with brotli 1.1.0, used once outside the repository: `python3 -m fontTools.subset Oswald-Bold.ttf --unicodes=U+0020-007E --flavor=woff2 --output-file=oswald-bold-latin.woff2` (all other options default; name IDs 0–6 kept). Two runs gave identical bytes |
| Embedded file | `oswald-bold-latin.woff2`, 11,844 bytes, 95 code points (U+0020–U+007E), weight 700, version 4.103 |
| Embedded SHA-256 | `299fca03acfe32ccf0b401b692ec66861173dd097ba3c5b61667117ff0afe033` |

To verify, fetch the source file at the pinned commit, check its SHA-256, rerun
the recipe with the same fontTools and brotli versions, and compare the output
with the embedded SHA-256. `test_page_design.py` pins the embedded file's
SHA-256, its data-only embedding and the page CSP, and checks in Chromium that
the face loads and only page headings use it. The version and weight above were
read with fontTools from the source and the output; the test does not reread them.

The OFL allows bundling and embedding with the licence. "Oswald" is not a
Reserved Font Name in this licence; the page still names its face `Oswald WR`,
because it is a subset.
