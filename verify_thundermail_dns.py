#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Check that a domain's DNS records match the Thundermail setup.

Verifies the MX record, the JMAP/CalDAV/CardDAV/IMAPS/submission SRV records,
the SPF / MTA-STS / TLSRPT / DMARC TXT records, and the three DKIM CNAMEs.

Usage:
    uv run verify_thundermail_dns.py <domain>
    uv run verify_thundermail_dns.py glamrocnamecheap.com
    uv run verify_thundermail_dns.py glamrocnamecheap.com --provider namecheap

Exit status is 0 only if every expected record is present and correct.

Pass --provider to print exactly what to enter in that DNS provider's control
panel for each FAILING record (accounting for provider quirks such as how the
Host/Name field is written). The supported providers come from records.json.
Fixes print as a compact per-type table by default; --fix-format long gives the
older one-labelled-block-per-record layout.

The record set, value templates, and per-provider remediation strings all live in
records.json, which is shared verbatim with the browser version (index.html /
app.js) so the two front-ends can never drift apart.

The resolver defaults to 1.1.1.1 (override with --resolver or DNS_RESOLVER) to
avoid stale local caches. The value may be an IP address or a hostname (e.g. an
authoritative nameserver such as dns1.registrar-servers.com), which is resolved
to its address before use.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import dns.rdatatype
import dns.resolver

CONFIG_PATH = Path(__file__).parent / "records.json"

GREEN = "\033[32m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

_TOKEN = re.compile(r"\{(\w+)\}")

# Control / terminal-escape bytes to neutralise in any DNS-derived text before
# printing (C0 minus \t\n\r, DEL, and C1). A domain owner controls their record
# contents, so this closes an ANSI-escape-injection path into the terminal.
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Hostname validation (kept in sync with the same regex in app.js). Applied to
# user-supplied domains before any lookup.
_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$"
)

_MAX_VALUE = 200  # cap displayed answer length to avoid pathological output


def sanitize(s: str) -> str:
    """Escape control/terminal chars so untrusted DNS data can't drive the tty."""
    return _CTRL.sub(lambda m: f"\\x{ord(m.group()):02x}", s)


def valid_domain(domain: str) -> bool:
    return bool(_HOSTNAME.match(domain))


def cap(s: str) -> str:
    return s if len(s) <= _MAX_VALUE else s[:_MAX_VALUE] + "…"


def label(rec: dict) -> str:
    return rec.get("label", rec["host"])


def resolve_record(rec: dict, domain: str) -> dict:
    """Concrete view of a record: {domain} filled in, plus qname/fqdn helpers.

    This is the shared "interpolation contract" — the JS twin in app.js does the
    same thing so templates in records.json render identically on both sides.
    """
    host = rec["host"]
    ctx = {k: (v.replace("{domain}", domain) if isinstance(v, str) else v)
           for k, v in rec.items()}
    ctx["domain"] = domain
    ctx["qname"] = domain if host == "@" else f"{host}.{domain}"
    ctx["fqdn"] = (domain + ".") if host == "@" else f"{host}.{domain}."
    # Relative host label, empty at the apex — for panels (e.g. Cosmotown) whose
    # Host field is left blank for the root domain rather than written as "@".
    ctx["subhost"] = "" if host == "@" else host
    return ctx


def interpolate(template: str, ctx: dict) -> str:
    """Replace {field} tokens in `template` with values from `ctx`."""
    return _TOKEN.sub(lambda m: str(ctx[m.group(1)]), template)


def value_of(ctx: dict, cfg: dict, key: str) -> str:
    """Render the 'value' (full) or 'match' (substring) string for a record."""
    return interpolate(cfg["value_templates"][ctx["type"]][key], ctx)


def render_fix(cfg: dict, provider: str, ctx: dict) -> list[str]:
    """Long form: provider instructions for one record (header + labelled fields)."""
    block = cfg["providers"][provider][ctx["type"]]
    width = max(len(lbl) for lbl, _ in block["fields"]) + 1  # + 1 for the colon
    lines = [block["header"]]
    for lbl, tpl in block["fields"]:
        lines.append(f"    {(lbl + ':'):<{width}} {interpolate(tpl, ctx)}")
    return lines


def render_fix_table(cfg: dict, provider: str, rtype: str, ctxs: list[dict]) -> list[str]:
    """Compact form: provider header, then one column per field and one row per
    failing record of the same type."""
    block = cfg["providers"][provider][rtype]
    labels = [lbl for lbl, _ in block["fields"]]
    rows = [[interpolate(tpl, ctx) for _, tpl in block["fields"]] for ctx in ctxs]
    widths = [max(len(labels[i]), *(len(r[i]) for r in rows)) for i in range(len(labels))]

    def fmt(cells: list[str]) -> str:  # left-align every column but the last
        return "  ".join(c if i == len(cells) - 1 else c.ljust(widths[i])
                         for i, c in enumerate(cells))

    return [block["header"], "", "  " + fmt(labels), *("  " + fmt(r) for r in rows)]


def build_resolver(server: str) -> dns.resolver.Resolver:
    """Return a resolver that queries `server` (IP or hostname) explicitly."""
    resolver = dns.resolver.Resolver(configure=False)
    try:
        # Accept a hostname (e.g. an authoritative NS) by resolving it first,
        # using the system resolver for that one lookup.
        addresses = [str(a) for a in dns.resolver.resolve(server, "A")]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException):
        # Assume `server` is already an IP address.
        addresses = [server]
    resolver.nameservers = addresses
    return resolver


def query(resolver: dns.resolver.Resolver, name: str, rdtype: str) -> list[str]:
    """Return answer records as strings, trailing dots trimmed (empty on none)."""
    try:
        answers = resolver.resolve(name, rdtype)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException):
        return []
    return [sanitize(answer.to_text().strip('"').rstrip(".")) for answer in answers]


def main() -> int:
    cfg = json.loads(CONFIG_PATH.read_text())
    providers = sorted(cfg["providers"])

    parser = argparse.ArgumentParser(
        description="Verify a domain's DNS matches the Thundermail setup.",
    )
    parser.add_argument("domain", help="domain to check, e.g. glamrocnamecheap.com")
    parser.add_argument(
        "--provider",
        choices=providers,
        help="print how to fix each FAILING record in this DNS provider's panel",
    )
    parser.add_argument(
        "--resolver",
        default=os.environ.get("DNS_RESOLVER", "1.1.1.1"),
        help="resolver IP or hostname to query (default: $DNS_RESOLVER or 1.1.1.1)",
    )
    parser.add_argument(
        "--fix-format",
        choices=("table", "long"),
        default="table",
        help="layout for --provider fixes: compact 'table' (default) or 'long' "
        "(one labelled block per record)",
    )
    args = parser.parse_args()

    domain = args.domain.strip().rstrip(".")
    if not valid_domain(domain):
        print(f"error: {sanitize(args.domain)!r} is not a valid domain name",
              file=sys.stderr)
        return 2

    resolver = build_resolver(args.resolver)

    print(f"Verifying Thundermail DNS for {domain} (resolver {sanitize(args.resolver)})\n")

    passed = 0
    failures = []
    current_group = None
    for rec in cfg["records"]:
        if rec["type"] != current_group:
            current_group = rec["type"]
            print(cfg["group_headers"][current_group])

        ctx = resolve_record(rec, domain)
        # Enrich with the derived match/value strings so provider templates can
        # reference {match} / {value} uniformly across record types.
        expected = ctx["match"] = value_of(ctx, cfg, "match")
        ctx["value"] = value_of(ctx, cfg, "value")
        actual = " / ".join(query(resolver, ctx["qname"], rec["type"]))
        shown = cap(actual)  # match on the full answer; display a bounded slice
        if expected.lower() in actual.lower():
            print(f"  {GREEN}OK{RESET}   {label(rec):<46} {shown}")
            passed += 1
        else:
            print(f"  {RED}FAIL{RESET} {label(rec):<46} expected to contain: {expected}")
            print(f"       {'':<46} got: {shown or '<empty>'}")
            failures.append(ctx)

    print(f"\nResult: {passed} passed, {len(failures)} failed.")

    if failures and args.provider:
        print(f"\n{BOLD}How to fix {len(failures)} record(s) in {args.provider}:{RESET}")
        if args.fix_format == "long":
            for ctx in failures:
                print(f"\n• {ctx['type']} {ctx.get('label', ctx['host'])}")
                for line in render_fix(cfg, args.provider, ctx):
                    print(f"  {line}")
        else:
            groups: dict[str, list[dict]] = {}  # group failures by type, in order
            for ctx in failures:
                groups.setdefault(ctx["type"], []).append(ctx)
            for rtype, ctxs in groups.items():
                print()
                for line in render_fix_table(cfg, args.provider, rtype, ctxs):
                    print(line)
    elif failures:
        choices = ", ".join(providers)
        print(f"\nRe-run with --provider ({choices}) to see exactly what to enter.")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
