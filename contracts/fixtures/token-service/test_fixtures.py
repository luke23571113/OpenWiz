#!/usr/bin/env python3
"""P1 (#1839): the token-service contract's pin, schema and fixtures agree.

Offline and credential-free: it reads only contracts/. Run it from anywhere:
python3 -I contracts/fixtures/token-service/test_fixtures.py
"""
import json
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
CONTRACTS = HERE.parent.parent
CONTRACT = CONTRACTS / "token-service.v1.md"
SCHEMA = CONTRACTS / "token-service.v1.schema.json"
IDENTITY = CONTRACTS / "github-identity.v1.md"
FIXTURES = ("requests.json", "refresh.json", "fallback.json", "invalid.json")
LEVEL = {"read": 0, "write": 1}

# A real credential's shapes (GitHub token prefixes, a JWT, a PEM block, a
# private key assignment) and any number long enough to be a real id.
CREDENTIAL = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{8,}|github_pat_|eyJ[A-Za-z0-9_-]{8,}\.|-----BEGIN|"
    r"PRIVATE KEY|(?<![0-9])[0-9]{8,}(?![0-9])")


def pin_of(path):
    blocks = re.findall(r"^```json\n(.*?)^```$", path.read_text(), re.M | re.S)
    return json.loads(blocks[0])


def strict(text):
    """A request as the service reads it: one JSON object, each key once, or None."""
    def once(pairs):
        keys = [k for k, _ in pairs]
        if len(set(keys)) != len(keys):
            raise ValueError("repeated key")
        return dict(pairs)
    try:
        value = json.loads(text, object_pairs_hook=once)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def resolve(schema, root):
    while "$ref" in schema:
        schema = root["$defs"][schema["$ref"].split("/")[-1]]
    return schema


def errors(value, schema, root, at="$"):
    """The subset of JSON Schema the contract's schema uses; a list of failures."""
    schema = resolve(schema, root)
    if "oneOf" in schema:
        passing = [s for s in schema["oneOf"] if not errors(value, s, root, at)]
        return [] if len(passing) == 1 else [f"{at}: matches {len(passing)} of oneOf"]
    kind = schema.get("type")
    checks = {"object": dict, "array": list, "string": str}
    if kind == "integer" and (type(value) is not int):
        return [f"{at}: not an integer"]
    if kind in checks and not isinstance(value, checks[kind]):
        return [f"{at}: not {kind}"]
    found = []
    if "const" in schema and value != schema["const"]:
        found.append(f"{at}: not {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        found.append(f"{at}: not in enum")
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        found.append(f"{at}: does not match {schema['pattern']}")
    if type(value) is int and value < schema.get("minimum", value):
        found.append(f"{at}: below minimum")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            found.append(f"{at}: too few items")
        if schema.get("uniqueItems") and len(set(map(json.dumps, value))) != len(value):
            found.append(f"{at}: repeated items")
        found += [e for i, item in enumerate(value)
                  for e in errors(item, schema.get("items", {}), root, f"{at}[{i}]")]
    if isinstance(value, dict):
        found += [f"{at}: missing {k}" for k in schema.get("required", []) if k not in value]
        if len(value) < schema.get("minProperties", 0):
            found.append(f"{at}: too few properties")
        properties = schema.get("properties", {})
        for key, item in value.items():
            names = schema.get("propertyNames")
            if names and errors(key, names, root):
                found.append(f"{at}: bad property name {key!r}")
            if key in properties:
                found += errors(item, properties[key], root, f"{at}.{key}")
            elif schema.get("additionalProperties") is False:
                found.append(f"{at}: unexpected {key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                found += errors(item, schema["additionalProperties"], root, f"{at}.{key}")
    return found


class Base(unittest.TestCase):
    def load(self, path):
        self.assertTrue(path.is_file(), f"{path.name} is missing")
        return json.loads(path.read_text())

    def setUp(self):
        self.assertTrue(CONTRACT.is_file(), "contracts/token-service.v1.md is missing")
        self.pin = pin_of(CONTRACT)
        self.schema = self.load(SCHEMA)
        self.fixtures = {name: self.load(HERE / name) for name in FIXTURES}

    def valid(self, message):
        return errors(message, self.schema, self.schema)


class ThePin(Base):
    def test_the_app_profile_and_token_guards_are_the_identity_contracts(self):
        # catches: a token-service profile or guard that drifts from github-identity.v1.
        identity = pin_of(IDENTITY)
        self.assertEqual(self.pin["schema"], "openwiz.token-service.v1")
        self.assertEqual(self.pin["app_permissions"], identity["app"]["permissions"])
        self.assertEqual(self.pin["answer"]["max_lifetime_s"],
                         identity["token_command"]["max_lifetime_s"])
        self.assertEqual(self.pin["refresh"]["at_or_under_s"],
                         identity["token_command"]["min_remaining_s"])

    def test_the_key_stays_on_the_owners_machine(self):
        # catches: a contract that lets the key travel or lets an agent ask for it.
        key = self.pin["key"]
        self.assertEqual(key["lives"], "owner's machine only")
        self.assertEqual(key["path"], "<state>/service/app/private-key.pem")
        self.assertEqual((key["file_mode"], key["directory_mode"]), ("0600", "0700"))
        self.assertEqual(key["agents"], "never ask for, read, copy or hold it")
        self.assertEqual(key["leaves_the_machine"], False)

    def test_the_service_has_no_port_and_takes_the_request_on_stdin(self):
        # catches: a reach route that opens a port or puts anything on a command line.
        reach = self.pin["reach"]
        self.assertEqual(reach["listens"], "no port")
        self.assertEqual(reach["request"], "stdin")
        for argv in reach["routes"].values():
            self.assertNotIn("token", " ".join(argv).lower())
        self.assertEqual(reach["routes"]["pairing"][:4], ["room-cli", "mac", "run", "--stdin"])

    def test_every_refusal_has_one_exit_and_one_fixed_sentence(self):
        # catches: a refusal code without a fixed exit or message the helper can rely on.
        refusals = self.pin["refusals"]
        enum = self.schema["$defs"]["refusal"]["properties"]["refusal"]["enum"]
        self.assertEqual(sorted(refusals), sorted(enum))
        for code, row in refusals.items():
            self.assertIn(row["exit"], (1, 2, 3, 5), code)
            self.assertRegex(row["message"], r"^[A-Z][^\n]*\.$", code)
        self.assertNotIn(0, [row["exit"] for row in refusals.values()])


class Requests(Base):
    def test_each_case_is_valid_and_its_outcome_follows_the_pin(self):
        # catches: a fixture outcome a service could not produce under the contract's rules.
        cases = self.fixtures["requests.json"]["cases"]
        app = self.pin["app_permissions"]
        installed = {r.lower() for r in self.fixtures["requests.json"]["installed"]}
        for case in cases:
            name, request, out = case["name"], case["request"], case["out"]
            if isinstance(request, str):
                request = strict(request)
            self.assertEqual(self.valid(out["message"]), [], name)
            if isinstance(request, dict) and not self.valid(request):
                repos = [r.lower() for r in request["repositories"]]
                if len({r.split("/")[0] for r in repos}) > 1:
                    want = "one-owner"
                elif not set(repos) <= installed:
                    want = "not-installed"
                elif any(p not in app or LEVEL[v] > LEVEL[app[p]]
                         for p, v in request["permissions"].items()):
                    want = "permission"
                else:
                    want = case.get("github", "answer")
            else:
                want = "usage"
            message = out["message"]
            got = message["refusal"] if message["kind"] == "refusal" else "answer"
            self.assertEqual(got, want, name)
            if got == "answer":
                self.assertEqual(out["exit"], 0, name)
                self.assertEqual(message["repositories"], request["repositories"], name)
                self.assertEqual(message["permissions"], request["permissions"], name)
                life = message["expires_at"] - self.fixtures["requests.json"]["now"]
                self.assertTrue(self.pin["refresh"]["at_or_under_s"] < life
                                <= self.pin["answer"]["max_lifetime_s"], name)
            else:
                row = self.pin["refusals"][got]
                self.assertEqual((out["exit"], message["message"]),
                                 (row["exit"], row["message"]), name)
            self.assertEqual(out["stderr"], "", name)
            log = out["log"]
            self.assertEqual(self.valid(log), [], name)
            self.assertEqual(log["outcome"], "minted" if got == "answer" else got, name)

    def test_the_pin_reads_requests_strictly(self):
        # catches: a service that keeps the last of a repeated key or misses a case-only match.
        rules = self.pin.get("request", {})
        self.assertEqual(rules.get("repeated_key"), "usage")
        self.assertEqual(rules.get("repository_case"), "insensitive")
        names = {c["name"] for c in self.fixtures["requests.json"]["cases"]}
        self.assertIn("a request with a repeated key", names)
        self.assertIn("repository names match the installation in any case", names)

    def test_the_fixtures_cover_a_good_request_and_every_refusal(self):
        # catches: a refusal the contract names but no fixture shows.
        cases = self.fixtures["requests.json"]["cases"]
        outcomes = {c["out"]["message"].get("refusal", "answer") for c in cases}
        self.assertEqual(outcomes, {"answer", *self.pin["refusals"]})


class RefreshAndFallback(Base):
    def test_a_token_is_refreshed_at_or_under_five_minutes_left(self):
        # catches: a helper that refreshes too late and lets a token expire mid-work.
        boundary = self.pin["refresh"]["at_or_under_s"]
        cases = self.fixtures["refresh.json"]["cases"]
        self.assertEqual({c["refresh"] for c in cases}, {True, False})
        self.assertIn(boundary, [c["expires_at"] - c["now"] for c in cases])
        for case in cases:
            self.assertEqual(case["refresh"], case["expires_at"] - case["now"] <= boundary,
                             case["name"])

    def test_the_fallback_says_so_once_and_not_configured_is_silent(self):
        # catches: a silent fallback, a repeated note, or a note when no service is set.
        note = self.pin["fallback"]["note"]
        reasons = set(self.pin["fallback"]["reasons"])
        self.assertEqual(reasons, {"unreachable", "bad-answer", *self.pin["refusals"]})
        seen = set()
        for case in self.fixtures["fallback.json"]["cases"]:
            name, out = case["name"], case["out"]
            if case["service"] == "not-configured":
                self.assertEqual((out["stderr"], out["identity"]), ("", "owner"), name)
            elif case["service"] == "answer":
                self.assertEqual((out["stderr"], out["identity"]), ("", "openwiz[bot]"), name)
            else:
                seen.add(case["reason"])
                self.assertEqual(out["stderr"], note.replace("<reason>", case["reason"]) + "\n",
                                 name)
                self.assertEqual(out["identity"], "owner", name)
                self.assertNotIn("GH_TOKEN", out["env"], name)
        self.assertIn("unreachable", seen)
        self.assertIn("bad-answer", seen)
        self.assertTrue(seen & set(self.pin["refusals"]))


class Invalid(Base):
    def test_every_invalid_message_fails_the_schema(self):
        # catches: a schema loose enough to accept a token in the log or a malformed answer.
        for case in self.fixtures["invalid.json"]["cases"]:
            self.assertNotEqual(self.valid(case["message"]), [], case["name"])


class NeverExposed(Base):
    def test_no_credential_or_real_id_in_the_contract_schema_or_fixtures(self):
        # catches: a real token, key or id committed in a contract file.
        for path in (CONTRACT, SCHEMA, *(HERE / n for n in FIXTURES)):
            self.assertIsNone(CREDENTIAL.search(path.read_text()), path.name)

    def test_the_scan_catches_what_it_claims(self):
        # catches: a scan pattern that silently stops matching.
        for planted in ("ghs_" + "A1b2C3d4E5", "github_pat_" + "x", "eyJ" + "hbGciOiJSUzI1.x",
                        "-----BEGIN" + " RSA", "123456789"):
            self.assertIsNotNone(CREDENTIAL.search(planted), planted)

    def test_a_token_appears_only_in_its_private_places(self):
        # catches: a token that reaches stderr, a log, an argument list or the environment's text.
        for name in ("requests.json", "fallback.json"):
            for case in self.fixtures[name]["cases"]:
                token = case["out"].get("message", {}).get("token") or case.get("token")
                if not token:
                    continue
                self.assertTrue(token.startswith("synthetic-"), case["name"])
                exposed = {k: v for k, v in case["out"].items() if k not in ("message", "env")}
                exposed["argv"] = case.get("argv", [])
                self.assertNotIn(token, json.dumps(exposed), case["name"])
                env = case["out"].get("env", {})
                self.assertEqual([k for k, v in env.items() if v == token],
                                 ["GH_TOKEN"] if "GH_TOKEN" in env else [], case["name"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
