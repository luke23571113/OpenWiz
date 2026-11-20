#!/usr/bin/env python3
"""The test-value campaign's measure (#803): coverage, test count, size and
run time for a group of Rust test targets, and the before-and-after compare.

  python3 -I tools/test-value/measure.py [--json FILE] TARGET...
  python3 -I tools/test-value/measure.py --all --json-dir DIR
  python3 -I tools/test-value/measure.py compare BEFORE.json AFTER.json

TARGET is NAME (a [[test]] of openwiz-tests) or PACKAGE:NAME. The method is
in README.md. Standard library only; installs its coverage tool itself.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time

SCHEMA = "openwiz.test-value.measure.v1"
LLVM_COV = "0.9.1"
DEFAULT_PACKAGE = "openwiz-tests"
TEST_CODE = ("tests/", "examples/", "benches/")
RESULT = re.compile(r"^test result: (\w+)\. (\d+) passed; (\d+) failed; (\d+) ignored;", re.M)


class MeasureError(Exception):
    pass


def coverage_by_crate(report, packages):
    """Covered and total lines per workspace crate, test code excluded.

    The openwiz-tests package is all test code, and so is every crate's
    tests/, examples/ and benches/, so a test that moves keeps the number."""
    roots = sorted(packages, key=lambda p: len(p[1]), reverse=True)
    out = {}
    for entry in report["data"][0]["files"]:
        path = entry["filename"]
        for name, root in roots:
            if not path.startswith(root + "/"):
                continue
            if name != DEFAULT_PACKAGE and not path[len(root) + 1:].startswith(TEST_CODE):
                lines = entry["summary"]["lines"]
                got = out.setdefault(name, [0, 0])
                got[0] += lines["covered"]
                got[1] += lines["count"]
            break
    return out


def parse_counts(text):
    """Passed and ignored tests over every libtest result line; a failed or
    missing run is an error, never a number."""
    results = RESULT.findall(text)
    if not results:
        raise MeasureError("no test result line: the run did not finish")
    if any(state != "ok" or int(failed) for state, _, failed, _ in results):
        raise MeasureError("a test failed: a red run is never measured")
    return {"passed": sum(int(r[1]) for r in results),
            "ignored": sum(int(r[3]) for r in results)}


def percent(pair):
    covered, count = pair
    return f"{covered * 100 / count:.2f}%" if count else "n/a"


def delta(a, b):
    return f"{a} -> {b} ({b - a:+d})"


def compare(before, after):
    """The before-and-after lines for a pull request."""
    for result in (before, after):
        if result.get("schema") != SCHEMA:
            raise MeasureError("not a measure result: wrong or missing schema")
    if before["toolchain"] != after["toolchain"]:
        raise MeasureError(f"different toolchains: {before['toolchain']} != {after['toolchain']}")
    lines = [f"before: {', '.join(before['targets'])}", f"after: {', '.join(after['targets'])}"]
    b_tests = before["tests"]["passed"] + before["tests"]["ignored"]
    a_tests = after["tests"]["passed"] + after["tests"]["ignored"]
    lines.append(f"tests: {delta(b_tests, a_tests)}")
    for key in ("files", "bytes", "lines"):
        lines.append(f"size {key}: {delta(before['size'][key], after['size'][key])}")
    drops = []
    for crate in sorted(set(before["coverage"]) | set(after["coverage"])):
        b = before["coverage"].get(crate, [0, 0])
        a = after["coverage"].get(crate, [0, 0])
        lines.append(f"coverage {crate}: {b[0]}/{b[1]} ({percent(b)}) -> "
                     f"{a[0]}/{a[1]} ({percent(a)}), covered {a[0] - b[0]:+d}")
        if a[0] < b[0]:
            drops.append(crate)
    lines.append(f"seconds: {before['seconds']} -> {after['seconds']} (not compared exactly)")
    lines.append(f"drops: {', '.join(drops) if drops else 'none'}")
    return lines


# Everything below runs cargo; the tests above cover the pure parts.

def run(cmd, cwd, env=None, check=True):
    proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True)
    if check and proc.returncode:
        sys.stderr.write(proc.stdout[-4000:])
        raise MeasureError(f"{' '.join(cmd)} exited {proc.returncode}")
    return proc


def tool_env(root):
    """Install cargo-llvm-cov at its pinned version in a private cache, never
    as a project dependency, and return the environment that finds it."""
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.environ["HOME"], ".cache")
    prefix = Path(cache) / "openwiz-test-value"
    env = dict(os.environ, PATH=f"{prefix / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
               CARGO_TERM_COLOR="never")
    installed = run(["cargo", "llvm-cov", "--version"], root, env, check=False)
    if installed.returncode or installed.stdout.split()[-1:] != [LLVM_COV]:
        print(f"installing cargo-llvm-cov {LLVM_COV} into {prefix}", file=sys.stderr)
        run(["rustup", "component", "add", "llvm-tools-preview"], root, env)
        run(["cargo", "install", "--locked", "cargo-llvm-cov", "--version", LLVM_COV,
             "--root", str(prefix)], root, env)
    return env


def toolchain(root, env):
    return {"rustc": run(["rustc", "--version"], root, env).stdout.strip(),
            "cargo-llvm-cov": run(["cargo", "llvm-cov", "--version"], root, env).stdout.strip()}


def metadata(root, env):
    data = json.loads(run(["cargo", "metadata", "--no-deps", "--format-version", "1"],
                          root, env).stdout)
    members = set(data["workspace_members"])
    return [p for p in data["packages"] if p["id"] in members]


def resolve(spec, packages):
    package, _, name = spec.rpartition(":")
    package = package or DEFAULT_PACKAGE
    for p in packages:
        if p["name"] == package:
            for t in p["targets"]:
                if t["name"] == name and "test" in t["kind"]:
                    return package, name, Path(t["src_path"])
    raise MeasureError(f"no test target {package}:{name}")


DEP = re.compile(r"(?:\\.|[^\s\\])+")


def sources(depinfos, root):
    """A group's own Rust sources, from rustc's dep-info for each test binary:
    every .rs file the compiler read for it inside this tree, outside target/,
    whatever its entrypoint is called or where its modules live. A file two
    targets share counts once. A dep-info naming none is refused."""
    root = str(root).rstrip("/")
    out = set()
    for text in depinfos:
        rule = text.split("\n", 1)[0].partition(": ")[2]
        # rustc names this tree's files relative to the workspace root, with
        # a #[path] module's `..` left in; others are absolute.
        deps = (os.path.normpath(os.path.join(root, re.sub(r"\\(.)", r"\1", m)))
                for m in DEP.findall(rule))
        own = {d for d in deps if d.endswith(".rs") and d.startswith(root + "/")
               and not d.startswith(root + "/target/")}
        if not own:
            raise MeasureError("a test binary's dep-info names none of this tree's sources")
        out |= own
    return sorted(out)


def size(files):
    data = [Path(p).read_bytes() for p in files]
    return {"files": len(data), "bytes": sum(len(d) for d in data),
            "lines": sum(d.count(b"\n") for d in data)}


def coverage_env(root, env):
    """cargo-llvm-cov's instrumented environment, in its own target folder so
    the plain build beside it stays as CI builds it."""
    env = dict(env, CARGO_TARGET_DIR=str(root / "target" / "test-value-cov"))
    for line in run(["cargo", "llvm-cov", "show-env"], root, env).stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and re.fullmatch(r"[A-Z_][A-Z0-9_]*", key):
            env[key] = shlex.split(value)[0] if value else ""
    return env


def prebuild(root, env):
    """The builds CI runs before its tests: ci.yml's workspace binaries and
    ci/rust-tests.sh's fixture release openwiz, which subprocess tests run.
    Also the debug fixture examples, which service's tests build themselves
    but one runs by its documented path under the default target folder."""
    run(["cargo", "build", "--locked", "--workspace", "--bins"], root, env)
    run(["cargo", "build", "--locked", "--release", "-p", DEFAULT_PACKAGE,
         "--example", "openwiz"], root, env)
    run(["cargo", "build", "--locked", "-p", DEFAULT_PACKAGE, "--examples"], root, env)


def test_run(root, env, select):
    proc = run(["cargo", "test", "--locked", *select], root, env)
    return parse_counts(proc.stdout)


def stray_profiles(root):
    """Raw profiles written into the checkout by child processes the tests
    start with a cleared environment (collect_profiles merges them)."""
    out = run(["git", "ls-files", "--others", "--exclude-standard", "-z", "--", "*.profraw"],
              root).stdout
    return {name for name in out.split("\0") if name}


def collect_profiles(root, before, dest):
    """Move the raw profiles that appeared since `before` (children a test
    started with a cleared environment write them into their working folder)
    into the report's folder, so their coverage counts; leave older files."""
    names = sorted(stray_profiles(root) - before)
    for n, name in enumerate(names):
        src = root / name
        target = dest / src.name
        if target.exists():
            target = dest / f"moved-{n}-{src.name}"
        shutil.move(str(src), str(target))
    return len(names)


def measure(root, specs, env):
    before = stray_profiles(root)
    try:
        return measure_once(root, specs, env, before)
    finally:
        for name in stray_profiles(root) - before:
            (root / name).unlink(missing_ok=True)


def dep_info(root, env, select, name):
    """The dep-info file rustc wrote beside the target's test binary."""
    out = run(["cargo", "test", "--locked", *select, "--no-run", "--message-format=json"],
              root, env).stdout
    for line in out.splitlines():
        msg = json.loads(line) if line.startswith("{") else {}
        target = msg.get("target", {})
        if (msg.get("reason") == "compiler-artifact" and target.get("name") == name
                and "test" in target.get("kind", []) and msg.get("executable")):
            path = Path(msg["executable"] + ".d")
            if path.is_file():
                return path.read_text()
    raise MeasureError(f"no dep-info for test target {name}")


def measure_once(root, specs, env, before):
    packages = metadata(root, env)
    targets = [resolve(s, packages) for s in specs]
    cov = coverage_env(root, env)
    run(["cargo", "llvm-cov", "clean", "--workspace"], root, cov)
    prebuild(root, cov)
    prebuild(root, env)
    counts = {"passed": 0, "ignored": 0}
    depinfos = []
    seconds = 0.0
    for package, name, src in targets:
        select = ["-p", package, "--test", name]
        counted = test_run(root, cov, select)
        collect_profiles(root, before, Path(cov["CARGO_LLVM_COV_TARGET_DIR"]))
        # Run time is the plain run's, as CI runs it, after its build.
        depinfos.append(dep_info(root, env, select, name))
        start = time.monotonic()
        if test_run(root, env, select) != counted:
            raise MeasureError(f"{package}:{name}: the plain and instrumented runs counted different tests")
        seconds += time.monotonic() - start
        for key, value in counted.items():
            counts[key] += value
        if os.path.normpath(src) not in sources(depinfos[-1:], root):
            raise MeasureError(f"{package}:{name}: its dep-info misses its own entrypoint")
    report = json.loads(run(["cargo", "llvm-cov", "report", "--json", "--summary-only"],
                            root, cov).stdout)
    roots = [(p["name"], str(Path(p["manifest_path"]).parent)) for p in packages]
    return {"schema": SCHEMA, "toolchain": toolchain(root, env),
            "targets": [f"{p}:{n}" for p, n, _ in targets], "tests": counts, "size": size(sources(depinfos, root)),
            "coverage": coverage_by_crate(report, roots), "seconds": round(seconds, 1)}


def show(result):
    lines = [f"targets: {', '.join(result['targets'])}",
             f"toolchain: {result['toolchain']['rustc']}; {result['toolchain']['cargo-llvm-cov']}",
             f"tests: {result['tests']['passed'] + result['tests']['ignored']} "
             f"(passed {result['tests']['passed']}, ignored {result['tests']['ignored']})",
             "size: {files} files, {bytes} bytes, {lines} lines".format(**result["size"])]
    pairs = result["coverage"].values()
    total = [sum(c for c, _ in pairs), sum(n for _, n in pairs)]
    for crate, pair in sorted(result["coverage"].items()):
        lines.append(f"coverage {crate}: {pair[0]}/{pair[1]} lines ({percent(pair)})")
    lines.append(f"coverage total: {total[0]}/{total[1]} lines ({percent(total)})")
    lines.append(f"seconds: {result['seconds']} (run time, outside the repeat check)")
    return lines


def write(path, result):
    Path(path).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def main(argv):
    if argv[:1] == ["compare"]:
        if len(argv) != 3:
            raise MeasureError("usage: measure.py compare BEFORE.json AFTER.json")
        before, after = (json.loads(Path(p).read_text()) for p in argv[1:])
        print("\n".join(compare(before, after)))
        return 0
    parser = argparse.ArgumentParser(prog="measure.py")
    parser.add_argument("targets", nargs="*", metavar="TARGET")
    parser.add_argument("--json", metavar="FILE", help="also write the result here")
    parser.add_argument("--all", action="store_true",
                        help="each [[test]] of openwiz-tests on its own (the baseline)")
    parser.add_argument("--json-dir", metavar="DIR", help="with --all: one <target>.json each")
    args = parser.parse_args(argv)
    if args.all == bool(args.targets) or (args.all and not args.json_dir):
        parser.error("give TARGET... or --all --json-dir DIR")
    root = Path(run(["git", "rev-parse", "--show-toplevel"], os.getcwd()).stdout.strip())
    env = tool_env(root)
    if args.all:
        tests = next(p for p in metadata(root, env) if p["name"] == DEFAULT_PACKAGE)
        names = sorted(t["name"] for t in tests["targets"] if "test" in t["kind"])
        Path(args.json_dir).mkdir(parents=True, exist_ok=True)
        for name in names:
            result = measure(root, [name], env)
            write(Path(args.json_dir) / f"{name}.json", result)
            print("\n".join(show(result)) + "\n", flush=True)
        return 0
    result = measure(root, args.targets, env)
    if args.json:
        write(args.json, result)
    print("\n".join(show(result)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except MeasureError as error:
        print(f"measure.py: {error}", file=sys.stderr)
        sys.exit(1)
