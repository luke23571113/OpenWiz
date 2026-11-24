# A fake key-host driver whose live host refuses effort

Login: held by Devin
Effort: passed as the `effort` field of the start request

The kit's own fixture: the effort key-host fixture, except that against the live host (the test's, not the kit's fake host) it refuses effort with a `next` other than the refusal text, before it sends any request.

The key is your `DEVIN_API_KEY`, or the keychain entry `openwiz-devin`; the driver never sees it.
