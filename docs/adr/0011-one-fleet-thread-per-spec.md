# One logical fleet owner per spec

Each spec has one logical fleet owner: the current admitted generation claim, shared by project and spec ticks, not the thread that started an agent. GitHub stays its only memory, so a replacement takes over from the records and talks to the orchestrator only through GitHub records. A standby outside the PC's failure domain records intents on GitHub, and each recipient reads them on its own wake; nobody archives or replaces a live builder to gain access. Every effect stays disabled at OB3's boundary until its actual endpoint checks generation and operation (OB-A1), and the access itself stays Unverified until #2244's discovery and OB8's live run. This refines ADR 0007 (the loop stays separate from the orchestrator).

Source: Jake, 2026-11-12, spec #2185 revisions 7/8 ([private record](https://github.com/jparker2006/ClosedWiz/issues/2185#issuecomment-6815747648)).
