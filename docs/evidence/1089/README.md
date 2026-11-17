# #1089: a cancelled upload's clean-up never fails a racing upload

Fixture evidence only. No live claim.

**Bug.** A staging reserves its room with a locked `.reserve` file in its own
folder. When an upload is cut off, its staging deletes that folder while it
still holds the lock. Another upload reserving room at that moment scans every
folder whose reservation is held (`Store::outstanding` in
`crates/store/src/attachments.rs`): it found the lock held, read the reserved
size, then listed a folder that was already gone. The listing's
`No such file or directory` became a store error, and the web API answered
`500 store_unavailable`.

**What existing tests missed.** No test ran a reservation scan while another
staging deleted its folder. AW5 met the race by chance (#946); #1083 only makes
that test wait for clean-up first.

**Proof.** `tests/attachments/ap07_low_disk.rs`,
`an_upload_cancelled_while_another_reserves_room_never_fails_it`. The test plays
the cancelled staging as another process would: it holds a folder's reservation
locked. Its `.reserve` is a FIFO, so the test can see the racing upload
reading it (the full pipe drains) and can hold that read while it deletes the
folder. There is no sleep and no retry. Deterministic: 5 of 5 red, 5 of 5 green,
about 10 ms each.

- Red, before the fix (`red.txt`, committed first): the racing upload returns
  `StoreError("could not list …/att-syn1089cancelled: No such file or directory")`.
- Green, after it: the racing upload stages, and only its own folder is left.

**Cross-check with #1083's interleaving probe.** This used
`docs/evidence/946/run-probe.py` and `reservation-race.c` from
`fix/946-upload-gate`, unchanged, with main's AW5 test, which has no #1083
wait. It holds a real aborted upload's clean-up until the next upload's scan has
read the reservation. On the red commit it prints
`probe: aborted reservation removed between scan read and directory listing`,
then fails with `500` / `store_unavailable`. With the fix, the same probe and
marker pass (`probe-green.txt`).

**Fix.** In `outstanding`, a folder that is gone while it is being looked at
needs no room: its staging ended. This covers `NotFound` from the listing and
from part-way through it (Linux returns `ENOENT` for a deleted directory). Every
other error still fails closed. The scan still runs under the claims lock, and
the free-disk floor, the reservation lock and its parse are unchanged.

Reproduce: `cargo test -p openwiz-tests --test attachments an_upload_cancelled`.
