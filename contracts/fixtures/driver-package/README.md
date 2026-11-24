# Driver package fixtures

Run from the checkout root:

```sh
python3 -I contracts/fixtures/driver-package/test_fixtures.py
```

The proof uses only the standard library. Its schema walker covers the
keywords this contract uses and refuses unknown ones. It does not act as
the installer: it reports the complete set of violations in a fixture
so a different failure cannot mask the intended one. It never extracts
or runs any archive member. The synthetic kit commit stands for the
checkout's kit schema bytes in this offline proof.

Each directory has the three release assets and a `package.json` that
could appear as a listing's package block. `cases.json` gives the one
intended refusal for each broken package. The wrong-checksum case
changes the listing hash, not the asset's own checksums file. The
changed-schema case contains valid JSON whose bytes are different;
both its member and archive hashes match. The wrong-driver-name case
changes the manifest name, not the selected driver's static name.

`shape-cases.json` contains isolated schema violations. `key_host.json`,
`pin.json` and `approval.json` are valid shapes. The pin's receipt URL is
synthetic and is not dereferenced. None of this is a live receipt,
fetch, install, approval or update.
