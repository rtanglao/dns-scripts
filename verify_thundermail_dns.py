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

Pass --provider to print, for each FAILING record, exactly what to enter in that
DNS provider's control panel (accounting for provider quirks such as how the
Host/Name field is written). Supported: namecheap, squarespace, generic.

The resolver defaults to 1.1.1.1 (override with --resolver or DNS_RESOLVER) to
avoid stale local caches. The value may be an IP address or a hostname (e.g. an
authoritative nameserver such as dns1.registrar-servers.com), which is resolved
to its address before use.
"""

import argparse
import os
import sys

import dns.rdatatype
import dns.resolver

MAIL_TARGET = "mail.thundermail.com"

GREEN = "\033[32m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Single source of truth for every record: drives both the verification checks
# and the per-provider remediation output. `host` is the sub-name under the
# domain ("@" == the root/apex). {domain} placeholders are filled at runtime.
RECORDS = [
    {"type": "MX", "host": "@", "priority": 10, "target": MAIL_TARGET},
    {"type": "SRV", "host": "_jmap._tcp", "priority": 0, "weight": 1, "port": 443, "target": MAIL_TARGET},
    {"type": "SRV", "host": "_caldavs._tcp", "priority": 0, "weight": 1, "port": 443, "target": MAIL_TARGET},
    {"type": "SRV", "host": "_carddavs._tcp", "priority": 0, "weight": 1, "port": 443, "target": MAIL_TARGET},
    {"type": "SRV", "host": "_imaps._tcp", "priority": 0, "weight": 1, "port": 993, "target": MAIL_TARGET},
    {"type": "SRV", "host": "_submission._tcp", "priority": 0, "weight": 1, "port": 587, "target": MAIL_TARGET},
    {"type": "TXT", "host": "@", "label": "@ (SPF)",
     "value": "v=spf1 include:spf.thundermail.com -all",
     "match": "v=spf1 include:spf.thundermail.com -all"},
    {"type": "TXT", "host": "_mta-sts",
     "value": "v=STSv1; id=18139500144460329770", "match": "v=STSv1;"},
    {"type": "TXT", "host": "_smtp._tls",
     "value": "v=TLSRPTv1; rua=mailto:postmaster@{domain}", "match": "v=TLSRPTv1;"},
    {"type": "TXT", "host": "_dmarc", "value": "v=DMARC1; p=none;", "match": "v=DMARC1;"},
    {"type": "CNAME", "host": "tm1._domainkey", "target": "tm1.{domain}.dkim.thunderhosted.com"},
    {"type": "CNAME", "host": "tm2._domainkey", "target": "tm2.{domain}.dkim.thunderhosted.com"},
    {"type": "CNAME", "host": "tm3._domainkey", "target": "tm3.{domain}.dkim.thunderhosted.com"},
]

GROUP_HEADERS = {"MX": "MX:", "SRV": "SRV:", "TXT": "TXT:", "CNAME": "CNAME (DKIM):"}


def label(rec: dict) -> str:
    return rec.get("label", rec["host"])


def query_name(rec: dict, domain: str) -> str:
    """Fully-qualified name to look up for this record."""
    if rec["host"] == "@":
        return domain
    return f"{rec['host']}.{domain}"


def expected_match(rec: dict, domain: str) -> str:
    """Substring the live answer must contain for the record to count as correct."""
    t = rec["type"]
    if t == "MX":
        return f"{rec['priority']} {rec['target']}"
    if t == "SRV":
        return f"{rec['priority']} {rec['weight']} {rec['port']} {rec['target']}"
    if t == "TXT":
        return rec["match"].format(domain=domain)
    if t == "CNAME":
        return rec["target"].format(domain=domain)
    raise ValueError(f"unknown record type {t!r}")


def full_value(rec: dict, domain: str) -> str:
    """The complete value to enter (for remediation / display)."""
    t = rec["type"]
    if t == "MX":
        return rec["target"]
    if t == "SRV":
        return f"{rec['weight']} {rec['port']} {rec['target']}"
    if t == "TXT":
        return rec["value"].format(domain=domain)
    if t == "CNAME":
        return rec["target"].format(domain=domain)
    raise ValueError(f"unknown record type {t!r}")


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
    return [answer.to_text().strip('"').rstrip(".") for answer in answers]


# --- Provider-specific remediation --------------------------------------------

def fix_namecheap(rec: dict, domain: str) -> list[str]:
    """How to enter `rec` in Namecheap's Advanced DNS panel.

    Namecheap auto-appends the domain to the Host field, so the Host is just the
    sub-name ("@" for the apex) and values carry no trailing dot.
    """
    t = rec["type"]
    if t == "MX":
        return [
            "Namecheap → Advanced DNS → Mail Settings: set 'Custom MX', then add:",
            "    Type:     MX Record",
            f"    Host:     {rec['host']}",
            f"    Value:    {rec['target']}",
            f"    Priority: {rec['priority']}",
        ]
    if t == "SRV":
        return [
            "Namecheap → Advanced DNS → Add New Record → SRV Record:",
            f"    Host:     {rec['host']}",
            f"    Priority: {rec['priority']}",
            f"    Weight:   {rec['weight']}",
            f"    Port:     {rec['port']}",
            f"    Target:   {rec['target']}",
        ]
    if t == "TXT":
        return [
            "Namecheap → Advanced DNS → Add New Record → TXT Record:",
            f"    Host:  {rec['host']}",
            f"    Value: {full_value(rec, domain)}",
        ]
    if t == "CNAME":
        return [
            "Namecheap → Advanced DNS → Add New Record → CNAME Record:",
            f"    Host:  {rec['host']}",
            f"    Value: {full_value(rec, domain)}   (no trailing dot)",
        ]
    raise ValueError(f"unknown record type {t!r}")


def fix_squarespace(rec: dict, domain: str) -> list[str]:
    """How to enter `rec` in Squarespace's DNS custom-records editor.

    Squarespace calls the sub-name field 'Name' ('@' for the apex, the sub-name
    only for subdomains — it appends the domain). MX/SRV have a separate Priority
    field; for SRV the 'Data' field holds 'weight port target' (space-separated).
    """
    prefix = "Squarespace → Domains → your domain → DNS → Custom Records → add:"
    t = rec["type"]
    if t == "MX":
        return [
            prefix,
            "    Type:     MX",
            f"    Name:     {rec['host']}",
            f"    Priority: {rec['priority']}",
            f"    Data:     {rec['target']}",
        ]
    if t == "SRV":
        return [
            prefix,
            "    Type:     SRV",
            f"    Name:     {rec['host']}",
            f"    Priority: {rec['priority']}",
            f"    Data:     {full_value(rec, domain)}",
        ]
    if t in ("TXT", "CNAME"):
        return [
            prefix,
            f"    Type: {t}",
            f"    Name: {rec['host']}",
            f"    Data: {full_value(rec, domain)}",
        ]
    raise ValueError(f"unknown record type {t!r}")


def fix_generic(rec: dict, domain: str) -> list[str]:
    """Provider-neutral record description (FQDN name, trailing dot)."""
    name = domain + "." if rec["host"] == "@" else f"{rec['host']}.{domain}."
    priority = rec.get("priority", "-") if rec["type"] in ("MX", "SRV") else "-"
    lines = [
        "Add this DNS record:",
        f"    Type:     {rec['type']}",
        f"    Name:     {name}",
        f"    Value:    {expected_match(rec, domain)}",
    ]
    if rec["type"] in ("MX", "SRV"):
        lines.append(f"    Priority: {priority}")
    return lines


PROVIDERS = {
    "namecheap": fix_namecheap,
    "squarespace": fix_squarespace,
    "generic": fix_generic,
}


# --- Verification --------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a domain's DNS matches the Thundermail setup.",
    )
    parser.add_argument("domain", help="domain to check, e.g. glamrocnamecheap.com")
    parser.add_argument(
        "--provider",
        choices=sorted(PROVIDERS),
        help="print how to fix each FAILING record in this DNS provider's panel",
    )
    parser.add_argument(
        "--resolver",
        default=os.environ.get("DNS_RESOLVER", "1.1.1.1"),
        help="resolver IP or hostname to query (default: $DNS_RESOLVER or 1.1.1.1)",
    )
    args = parser.parse_args()

    resolver = build_resolver(args.resolver)
    fixer = PROVIDERS[args.provider] if args.provider else None

    print(f"Verifying Thundermail DNS for {args.domain} (resolver {args.resolver})\n")

    passed = 0
    failures = []
    current_group = None
    for rec in RECORDS:
        if rec["type"] != current_group:
            current_group = rec["type"]
            print(GROUP_HEADERS[current_group])

        actual = " / ".join(query(resolver, query_name(rec, args.domain), rec["type"]))
        expected = expected_match(rec, args.domain)
        if expected.lower() in actual.lower():
            print(f"  {GREEN}OK{RESET}   {label(rec):<46} {actual}")
            passed += 1
        else:
            print(f"  {RED}FAIL{RESET} {label(rec):<46} expected to contain: {expected}")
            print(f"       {'':<46} got: {actual or '<empty>'}")
            failures.append(rec)

    print(f"\nResult: {passed} passed, {len(failures)} failed.")

    if failures and fixer:
        print(f"\n{BOLD}How to fix {len(failures)} record(s) in {args.provider}:{RESET}")
        for rec in failures:
            print(f"\n• {rec['type']} {label(rec)}")
            for line in fixer(rec, args.domain):
                print(f"  {line}")
    elif failures:
        choices = ", ".join(sorted(PROVIDERS))
        print(f"\nRe-run with --provider ({choices}) to see exactly what to enter.")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
