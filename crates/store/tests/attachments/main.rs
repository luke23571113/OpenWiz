//! The attachment staging proof cases that need only `openwiz-store` (#14):
//! AP4's order of durable steps and what is never ready, AP5's swapped
//! source, AP7's free-disk floor and its `df` reader. Moved here from
//! `tests/attachments` by #810; the cases that run `openwiz attachment`,
//! a child process or another program stay there.
//!
//! **Fixtures only.** The synthetic files are written at test time into a
//! private directory under the system's temporary directory (never
//! committed, never inside the repository), with a faked free-space
//! measure; nothing calls `room-cli`.

mod bench;

mod ap04_ready;
mod ap05_originals;
mod ap07_low_disk;
