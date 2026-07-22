#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Python↔JS interpreter parity.

The CLI (verify_thundermail_dns.py) and the web app (app.js) duplicate the same
tiny interpreter, and CLAUDE.md's #1 rule is that they must never drift. This
test runs a shared fixture (tests/fixtures/parity_cases.json) through the Python
functions and, via a Node harness (tests/parity/run_js.mjs), through the JS ones,
then asserts the results are identical. Skips gracefully if `node` is missing.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

import verify_thundermail_dns as v

ROOT = Path(__file__).parent.parent
CFG = json.loads((ROOT / "records.json").read_text())
CASES = json.loads((Path(__file__).parent / "fixtures" / "parity_cases.json").read_text())
HARNESS = Path(__file__).parent / "parity" / "run_js.mjs"


def python_results() -> dict:
    match = [v.matches(c["expected"], c["answers"], c["mode"])
             for c in CASES["matchCases"]]
    resolve = []
    for c in CASES["resolveCases"]:
        ctx = v.resolve_record(c["record"], c["domain"])
        ctx["match"] = v.value_of(ctx, CFG, "match")
        ctx["value"] = v.value_of(ctx, CFG, "value")
        resolve.append({k: ctx[k] for k in (
            "qname", "fqdn", "subhost", "service", "protocol",
            "srvhost", "srvsubhost", "match", "value")})
    return {"match": match, "resolve": resolve}


@unittest.skipUnless(shutil.which("node"), "node not installed")
class TestParity(unittest.TestCase):
    def test_js_matches_python(self):
        payload = json.dumps({
            "cfg": CFG,
            "matchCases": CASES["matchCases"],
            "resolveCases": CASES["resolveCases"],
        })
        proc = subprocess.run(
            ["node", str(HARNESS)],
            input=payload, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, f"node harness failed:\n{proc.stderr}")
        js = json.loads(proc.stdout)
        py = python_results()

        # Sanity: the fixture's declared verdicts agree with Python's matcher.
        for case, got in zip(CASES["matchCases"], py["match"]):
            self.assertEqual(got, case["verdict"], case["name"])

        self.assertEqual(js["match"], py["match"], "matches() diverged")
        self.assertEqual(js["resolve"], py["resolve"],
                         "resolve_record/value_of diverged")


if __name__ == "__main__":
    unittest.main()
