"""DR1 offline proof; no extracted files, driver execution or network I/O."""
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
import unittest

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
CONTRACTS = HERE.parents[1]


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate JSON key")
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def tar_members(data):
    raw = gzip.decompress(data)
    offset = 0
    while raw[offset:offset + 512] != bytes(512):
        member = tarfile.TarInfo.frombuf(raw[offset:offset + 512], "ascii", "strict")
        offset += 512
        yield member, raw[offset:offset + member.size]
        offset += ((member.size + 511) // 512) * 512
    if len(raw) - offset < 1024 or any(raw[offset:]):
        raise ValueError("invalid tar trailer")


def package_rules(package, manifest, archive, kit_schema):
    failures = set()
    release_url = (f"https://github.com/{package['repository']}/releases/download/"
                   f"v{package['version']}/driver.tar.gz")
    if package["asset_url"] != release_url:
        failures.add("asset-repository")
    if package["sha256"] != digest(archive):
        failures.add("archive-sha256")
    if manifest["driver"] != package["driver"]:
        failures.add("driver-name")
    if any(manifest[key] != package[key] for key in ("version", "kit_commit")):
        failures.add("release-identity")

    entries = {entry["path"]: entry for entry in manifest["files"]}
    if len(entries) != len(manifest["files"]):
        failures.add("duplicate-manifest-path")
    seen = set()
    for member, data in tar_members(archive):
        path = member.name
        if path in seen:
            failures.add("duplicate-member")
        seen.add(path)
        if path not in entries:
            failures.add("extra-file")
        if member.type != tarfile.REGTYPE:
            failures.add("member-type")
            continue
        if path in entries:
            if entries[path]["mode"] != f"{member.mode:04o}":
                failures.add("member-mode")
            if entries[path]["sha256"] != digest(data):
                failures.add("member-sha256")
        if path == "schema.json" and data != kit_schema:
            failures.add("kit-schema")
    if entries.keys() - seen:
        failures.add("missing-file")
    return failures


class DriverPackageFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = read_json(CONTRACTS / "driver-package.v1.schema.json")
        Draft202012Validator.check_schema(cls.schema)

    def errors(self, kind, value):
        ref = {"$ref": f"#/$defs/{kind}"} if "$defs" in self.schema else {}
        validator = Draft202012Validator(self.schema).evolve(schema=ref)
        return sorted(("/".join(map(str, e.path)), e.validator) for e in validator.iter_errors(value))

    def test_package_refusals_are_isolated(self):
        kit_schema = (CONTRACTS.parent / "kernel/driver-kit/schema.json").read_bytes()
        cases = read_json(HERE / "cases.json")
        self.assertEqual(set(cases), {p.name for p in HERE.iterdir() if p.is_dir()})
        for case, refusal in cases.items():
            with self.subTest(case=case):
                folder = HERE / case
                package = read_json(folder / "package.json")
                manifest = read_json(folder / "manifest.json")
                archive = (folder / "driver.tar.gz").read_bytes()
                self.assertEqual([], self.errors("package", package))
                self.assertEqual([], self.errors("manifest", manifest))
                sums = "".join(f"{digest((folder / name).read_bytes())}  {name}\n"
                               for name in ("driver.tar.gz", "manifest.json"))
                self.assertEqual(sums, (folder / "SHA256SUMS").read_text())
                self.assertEqual({refusal} if refusal else set(),
                                 package_rules(package, manifest, archive, kit_schema))

    def test_record_shapes_accept_good_and_refuse_one_field(self):
        for kind in ("key_host", "pin", "approval"):
            with self.subTest(kind=kind):
                self.assertEqual([], self.errors(kind, read_json(HERE / f"{kind}.json")))
        for case in read_json(HERE / "shape-cases.json"):
            with self.subTest(kind=case["kind"], error=case["error"]):
                self.assertEqual([tuple(case["error"])], self.errors(case["kind"], case["value"]))


if __name__ == "__main__":
    unittest.main()
