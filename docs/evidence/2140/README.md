# #2140 evidence: the README and install guide against the 0.1.0 package

`check_docs.py` is this ticket's proof. From the repository root:

```sh
python3 -I docs/evidence/2140/check_docs.py <unpacked openwiz-0.1.0-x86_64-unknown-linux-gnu package>
```

It reads `README.md` and `docs/install.md` and prints one line per failure:

1. **No stale words:** a "coming soon" 0.1.0, 0.0.12 as current, the removed setup page, port 7370, `install open`, or Intel Mac listed as supported or sent to a CloudRoom installer (CloudRoom offers no Intel Mac build).
2. **Every link resolves:** a relative link to a file Git tracks (a gitignored path such as `skills/` is a 404 on GitHub), a web link to an HTTP status below 400, redirects followed.
3. **No whole-folder delete:** no instruction deletes the install folder itself (`rm -rf <root>`, "delete the install folder", "remove the install"), because the installer accepts a folder that already holds other files.
4. **Every command exists:** each `tools/install/install <command>` is a command of this checkout's installer, and each `runtime/<tool>.py <command>` is a command of that tool in the unpacked 0.1.0 package (its `--help` exits 0).

Exit 0 when all hold, 1 otherwise. It reads only and installs nothing. The package came from `https://github.com/openwizdev/OpenWiz/releases/download/v0.1.0/`, with its SHA-256 checked against the release's `SHA256SUMS`.

- `red.txt`: the run at `main` before the fix (exit 1).
- `red-intel-mac.txt`: the run after the Intel Mac checks were added, before those lines were fixed (exit 1).
- `red-whole-root.txt`: the run after the whole-folder check was added, before the removal and repair steps were fixed (exit 1).
- `green.txt`: the run on this branch's docs (exit 0).
