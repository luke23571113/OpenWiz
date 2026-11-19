#!/usr/bin/env python3
"""Print an installation token for GH_TOKEN, minting only when needed (G2, #1402).

Takes mint-token.py's options. Stdout is the token alone, so
`GH_TOKEN="$(python3 -I refresh-token.py ...)"` works as is; nothing else is
printed on success. A token is reused while more than five minutes of it are
left, then a fresh one is minted. Each scope (API, installation, repositories,
profile, key source) has its own cache entry in <state>/tokens/, owner-only
(0700 directory, 0600 files, never a symlink), so another scope never gets it.
An unsafe cache is refused, never used.
"""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

import app

spec = importlib.util.spec_from_file_location("mint_token", Path(__file__).with_name("mint-token.py"))
minter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(minter)

# Refresh with five minutes or less left (contracts/github-identity.v1.md's boundary).
REFRESH = 300
TOKEN = re.compile(r"[A-Za-z0-9._~+/-]+=*")


def tokens_directory(state):
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        app.checked(fd, directory=True)
        try:
            os.mkdir("tokens", mode=0o700, dir_fd=fd)
        except FileExistsError:
            pass
        child = os.open("tokens", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
    finally:
        os.close(fd)
    try:
        return app.checked(child, directory=True)
    except Exception:
        os.close(child)
        raise


def cached(directory, name):
    """The cached (token, expiry), None when absent or unreadable as ours; an
    unsafe file (mode, owner, link) raises."""
    try:
        content = app.read_file(directory, name, 4096)
    except FileNotFoundError:
        return None
    try:
        value = app.parse_json(content)
    except ValueError:
        return None
    token, expiry = value.get("token"), value.get("expires_at")
    if set(value) != {"token", "expires_at"} or not isinstance(token, str) \
            or TOKEN.fullmatch(token) is None or type(expiry) is not int:
        return None
    return token, expiry


def save(directory, name, token, expiry):
    temporary = f".{name}.{os.getpid()}"
    try:
        os.unlink(temporary, dir_fd=directory)
    except FileNotFoundError:
        pass
    app.save_file(directory, temporary, json.dumps({"token": token, "expires_at": expiry}).encode())
    os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)


def main():
    args = minter.parser(__doc__).parse_args()
    selected = minter.selection(args)
    scope = [args.api_base, args.installation_id, selected, args.write, args.from_secret,
             os.environ.get(app.SECRET_ID) if args.from_secret else None]
    name = hashlib.sha256(json.dumps(scope).encode()).hexdigest()[:32] + ".json"
    directory = tokens_directory(app.state_path(args.state_dir))
    try:
        lock = os.open(".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            app.checked(lock)
            fcntl.flock(lock, fcntl.LOCK_EX)  # one mint at a time per state
            found = cached(directory, name)
            if found is None or not REFRESH < found[1] - time.time() <= 3600 + 300:
                found = minter.mint(args, selected)
                app.require(found[1] - time.time() > REFRESH)
                save(directory, name, *found)
        finally:
            os.close(lock)
    finally:
        os.close(directory)
    print(found[0])


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        print("App token refused: check PC state permissions, App installation and GitHub availability.",
              file=sys.stderr)
        sys.exit(1)
