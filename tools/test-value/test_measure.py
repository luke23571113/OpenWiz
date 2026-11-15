#!/usr/bin/env python3
"""#803: the contracts later groups rely on in measure.py, on synthetic input.

Run: python3 -I tools/test-value/test_measure.py
"""
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("measure", HERE / "measure.py")
measure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure)

ROOT = "/work/repo"
PACKAGES = [
    ("openwiz-core", f"{ROOT}/crates/core"),
    ("openwiz-store", f"{ROOT}/crates/store"),
    ("openwiz-tests", f"{ROOT}/tests"),
]


def file_entry(path, covered, count):
    return {"filename": path, "summary": {"lines": {"count": count, "covered": covered}}}


def report(*files):
    return {"type": "llvm.coverage.json.export", "data": [{"files": list(files)}]}


class CoverageByCrate(unittest.TestCase):
    # catches: test code counted as covered product code, so moving a test
    # from tests/ into crates/<crate>/tests/ (TV4 onward) changes the number.
    def test_counts_only_product_sources_per_crate(self):
        got = measure.coverage_by_crate(report(
            file_entry(f"{ROOT}/crates/core/src/lib.rs", 30, 40),
            file_entry(f"{ROOT}/crates/core/src/send/mod.rs", 5, 20),
            file_entry(f"{ROOT}/crates/core/tests/moved.rs", 90, 90),
            file_entry(f"{ROOT}/crates/store/src/lib.rs", 0, 12),
            file_entry(f"{ROOT}/crates/store/examples/demo.rs", 7, 7),
            file_entry(f"{ROOT}/tests/fleet/main.rs", 50, 50),
            file_entry(f"{ROOT}/tests/fake-room-cli/main.rs", 60, 80),
            file_entry("/outside/cargo-registry/src/serde/lib.rs", 3, 9),
        ), PACKAGES)
        self.assertEqual(got, {"openwiz-core": [35, 60], "openwiz-store": [0, 12]})


class TestCounts(unittest.TestCase):
    # catches: a target with several test binaries or result lines measured
    # by its first line only, or a red run saved as a baseline.
    def test_sums_every_result_line(self):
        out = (
            "running 3 tests\n"
            "test result: ok. 2 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out; finished in 0.10s\n"
            "running 4 tests\n"
            "test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 2.00s\n"
        )
        self.assertEqual(measure.parse_counts(out), {"passed": 6, "ignored": 1})

    def test_refuses_a_failed_or_missing_run(self):
        failed = "test result: FAILED. 3 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.00s\n"
        for out in (failed, "error: could not compile `openwiz-tests`\n"):
            with self.subTest(out=out), self.assertRaises(measure.MeasureError):
                measure.parse_counts(out)


def result(toolchain, coverage, tests=10):
    return {"schema": measure.SCHEMA, "toolchain": toolchain, "targets": ["openwiz-tests:fleet"],
            "tests": {"passed": tests, "ignored": 0}, "size": {"files": 2, "bytes": 100, "lines": 9},
            "coverage": coverage, "seconds": 1.0}


class Compare(unittest.TestCase):
    TOOLS = {"rustc": "rustc 1.99.1", "cargo-llvm-cov": "cargo-llvm-cov 0.9.1"}

    # catches: a before measured on another toolchain read as a coverage change.
    def test_refuses_different_toolchains(self):
        other = dict(self.TOOLS, rustc="rustc 1.98.0")
        with self.assertRaises(measure.MeasureError):
            measure.compare(result(self.TOOLS, {}), result(other, {}))

    # catches: a coverage drop in one crate hidden by a gain in another, or a
    # crate that disappears from the after report not reported as a drop.
    def test_names_every_crate_that_lost_covered_lines(self):
        lines = measure.compare(
            result(self.TOOLS, {"openwiz-core": [35, 60], "openwiz-store": [4, 12], "openwiz-cli": [8, 10]}),
            result(self.TOOLS, {"openwiz-core": [40, 60], "openwiz-store": [3, 12]}, tests=7))
        self.assertIn("drops: openwiz-cli, openwiz-store", lines)
        self.assertIn("tests: 10 -> 7 (-3)", lines)


if __name__ == "__main__":
    unittest.main()
