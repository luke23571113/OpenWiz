# Public-tree import

`import.py` builds the public tree from ClosedWiz for OpenWiz, checked by the [privacy check](../privacy-check/README.md). Python 3.11+ and Git only; it never fetches, pushes, checks out or moves a branch. Fetch both repositories' commits first. Keep the checker and its private literals list outside both repositories.

```sh
# a whole tree: one ordinary commit on top of the destination's main (a dry run unless --write-local)
python3 -I tools/open-import/import.py tree --source CLOSEDWIZ --commit SOURCE_COMMIT \
  --destination OPENWIZ --checker CHECK_PY --literals LIST [--write-local]
# a reviewed patch of public files for a source range, written to a new private folder
python3 -I tools/open-import/import.py patch --source CLOSEDWIZ --source-base BASE --commit HEAD \
  --destination OPENWIZ --checker CHECK_PY --literals LIST --output /private/patch
# apply that patch to OpenWiz, bound to the digest you reviewed
python3 -I tools/open-import/import.py apply-patch --destination OPENWIZ --patch-dir /private/patch \
  --binding-sha256 DIGEST --checker CHECK_PY --literals LIST [--write-local]
python3 -I tools/open-import/test_import.py           # offline proofs, real Git, synthetic roots
```

Exit 0 is checked, 1 refused or unreadable, 2 bad arguments; the result is JSON. `--write-local` saves only the checked commit's objects: no branch, index or worktree changes. `patch` writes `public.patch` and `binding.json`; keep the binding private and record its `binding_sha256` from the result. Any branch, push or pull request after that is a separate, gated step.

## The carriage list

`paths.json` decides what is carried. `source` patterns select public files; `keep` names destination files that survive and wins over `source`; `private/`, grills (but their README) and retiring kits are never carried. An unknown source path refuses the import.
