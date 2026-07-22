#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Hermetic tests for the CLI interpreter and records.json.

No DNS, no browser: every check runs against the pure functions in
verify_thundermail_dns.py (matching, token interpolation, record resolution,
provider rendering) plus a records.json linter. Run from the repo root:

    uv run python -m unittest discover -s tests -t . -v
"""

import json
import re
import unittest
from pathlib import Path

import verify_thundermail_dns as v

CFG = json.loads((Path(__file__).parent.parent / "records.json").read_text())
TOKEN = re.compile(r"\{(\w+)\}")


def build_ctx(rec: dict, domain: str = "example.com") -> dict:
    """Resolve a record exactly as main() does, so provider templates can be
    interpolated against it (adds the derived match/value strings)."""
    ctx = v.resolve_record(rec, domain)
    ctx["match"] = v.value_of(ctx, CFG, "match")
    ctx["value"] = v.value_of(ctx, CFG, "value")
    return ctx


class TestMatches(unittest.TestCase):
    def test_exact_rejects_appended_target(self):
        # #10 regression: a target with the zone name appended must not pass.
        self.assertFalse(v.matches(
            "0 1 443 mail.thundermail.com",
            ["0 1 443 mail.thundermail.com.emilio.me"],
            "exact",
        ))

    def test_exact_accepts_correct_target(self):
        self.assertTrue(v.matches(
            "0 1 443 mail.thundermail.com",
            ["0 1 443 mail.thundermail.com"],
            "exact",
        ))

    def test_exact_accepts_among_multiple_answers(self):
        self.assertTrue(v.matches(
            "10 mail.thundermail.com",
            ["20 backup.example.com", "10 mail.thundermail.com"],
            "exact",
        ))

    def test_exact_is_case_insensitive(self):
        self.assertTrue(v.matches(
            "tm1.example.com.dkim.thunderhosted.com",
            ["TM1.EXAMPLE.COM.DKIM.THUNDERHOSTED.COM"],
            "exact",
        ))

    def test_exact_rejects_empty(self):
        self.assertFalse(v.matches("10 mail.thundermail.com", [], "exact"))

    def test_contains_accepts_prefix_fragment(self):
        self.assertTrue(v.matches(
            "v=STSv1;", ["v=STSv1; id=18139500144460329770"], "contains"))

    def test_contains_rejects_absent_fragment(self):
        self.assertFalse(v.matches(
            "v=STSv1;", ["v=spf1 include:spf.thundermail.com -all"], "contains"))


class TestResolveRecord(unittest.TestCase):
    def test_apex_tokens(self):
        ctx = v.resolve_record({"type": "MX", "host": "@", "priority": 10,
                                "target": "mail.thundermail.com"}, "example.com")
        self.assertEqual(ctx["qname"], "example.com")
        self.assertEqual(ctx["fqdn"], "example.com.")
        self.assertEqual(ctx["subhost"], "")  # blank at apex (Cosmotown/bunny/ovh)

    def test_srv_apex_split_tokens(self):
        ctx = v.resolve_record({"type": "SRV", "host": "_jmap._tcp"}, "example.com")
        self.assertEqual(ctx["service"], "_jmap")
        self.assertEqual(ctx["protocol"], "_tcp")
        self.assertEqual(ctx["srvhost"], "@")     # "@" at apex (GoDaddy/IONOS)
        self.assertEqual(ctx["srvsubhost"], "")   # blank at apex (Hover)

    def test_srv_non_apex_rest_label(self):
        ctx = v.resolve_record({"type": "SRV", "host": "_sip._tcp.pbx"}, "example.com")
        self.assertEqual(ctx["srvhost"], "pbx")
        self.assertEqual(ctx["srvsubhost"], "pbx")
        self.assertEqual(ctx["qname"], "_sip._tcp.pbx.example.com")

    def test_domain_token_substituted(self):
        ctx = build_ctx({"type": "CNAME", "host": "tm1._domainkey",
                         "target": "tm1.{domain}.dkim.thunderhosted.com"})
        self.assertEqual(ctx["target"], "tm1.example.com.dkim.thunderhosted.com")
        self.assertEqual(ctx["value"], "tm1.example.com.dkim.thunderhosted.com")


class TestValueTemplates(unittest.TestCase):
    def test_every_type_has_match_value_mode(self):
        for rtype, tpl in CFG["value_templates"].items():
            self.assertIn("match", tpl, rtype)
            self.assertIn("value", tpl, rtype)
            self.assertIn(tpl.get("match_mode"), ("exact", "contains"), rtype)

    def test_target_bearing_types_are_exact(self):
        # MX/SRV/CNAME carry a target that must match a whole answer (see #10).
        for rtype in ("MX", "SRV", "CNAME"):
            self.assertEqual(CFG["value_templates"][rtype]["match_mode"], "exact")
        self.assertEqual(CFG["value_templates"]["TXT"]["match_mode"], "contains")


class TestRecordsJsonLint(unittest.TestCase):
    RECORD_TYPES = ("MX", "SRV", "TXT", "CNAME")

    def _sample_record(self, rtype: str) -> dict:
        return next(r for r in CFG["records"] if r["type"] == rtype)

    def test_every_provider_covers_every_type(self):
        for name, block in CFG["providers"].items():
            for rtype in self.RECORD_TYPES:
                self.assertIn(rtype, block, f"{name} missing {rtype}")

    def test_field_templates_reference_only_known_tokens(self):
        # Interpolating every field template against a resolved ctx must neither
        # raise (unknown token → KeyError) nor leave a residual {token}.
        for name, block in CFG["providers"].items():
            for rtype in self.RECORD_TYPES:
                ctx = build_ctx(self._sample_record(rtype))
                for label, tpl in block[rtype]["fields"]:
                    rendered = v.interpolate(tpl, ctx)
                    self.assertNotRegex(
                        rendered, TOKEN,
                        f"{name}.{rtype} field {label!r} left a token: {rendered!r}")

    def test_headers_have_no_unsubstituted_tokens(self):
        # Headers are printed verbatim (never interpolated), so any {token} in one
        # is a bug that would leak to the user.
        for name, block in CFG["providers"].items():
            for rtype in self.RECORD_TYPES:
                header = block[rtype]["header"]
                self.assertNotRegex(header, TOKEN, f"{name}.{rtype} header")


class TestProviderRenderGolden(unittest.TestCase):
    def _ctxs(self, rtype: str) -> list[dict]:
        return [build_ctx(r) for r in CFG["records"] if r["type"] == rtype]

    def test_digitalocean_srv_target_has_trailing_dot(self):
        rows = v.render_fix_table(CFG, "digitalocean", "SRV", self._ctxs("SRV"))
        body = "\n".join(rows)
        self.assertIn("mail.thundermail.com.", body)  # trailing dot preserved
        self.assertIn("_jmap._tcp", body)

    def test_namecheap_mx_row(self):
        rows = v.render_fix_table(CFG, "namecheap", "MX", self._ctxs("MX"))
        body = "\n".join(rows)
        self.assertIn("mail.thundermail.com", body)
        self.assertIn("10", body)

    def test_long_form_has_header_and_labels(self):
        ctx = build_ctx(self._sample_mx())
        lines = v.render_fix(CFG, "namecheap", ctx)
        self.assertTrue(lines[0].startswith("Namecheap"))
        self.assertTrue(any("Priority:" in ln for ln in lines))

    def _sample_mx(self) -> dict:
        return next(r for r in CFG["records"] if r["type"] == "MX")


if __name__ == "__main__":
    unittest.main()
