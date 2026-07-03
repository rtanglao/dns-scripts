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

Exit status is 0 only if every expected record is present and correct.

The resolver defaults to 1.1.1.1 (override with DNS_RESOLVER) to avoid stale
local caches. DNS_RESOLVER may be an IP address or a hostname (e.g. an
authoritative nameserver such as dns1.registrar-servers.com), which is resolved
to its address before use.
"""

import os
import sys

import dns.rdatatype
import dns.resolver

MAIL_TARGET = "mail.thundermail.com"

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


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


class Checker:
    def __init__(self, resolver: dns.resolver.Resolver, domain: str):
        self.resolver = resolver
        self.domain = domain
        self.passed = 0
        self.failed = 0

    def check(self, label: str, expected: str, name: str, rdtype: str) -> None:
        actual = " / ".join(query(self.resolver, name, rdtype))
        if expected.lower() in actual.lower():
            print(f"  {GREEN}OK{RESET}   {label:<46} {actual}")
            self.passed += 1
        else:
            print(f"  {RED}FAIL{RESET} {label:<46} expected to contain: {expected}")
            print(f"       {'':<46} got: {actual or '<empty>'}")
            self.failed += 1


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <domain>", file=sys.stderr)
        return 2
    domain = sys.argv[1]
    server = os.environ.get("DNS_RESOLVER", "1.1.1.1")
    resolver = build_resolver(server)

    print(f"Verifying Thundermail DNS for {domain} (resolver {server})\n")
    c = Checker(resolver, domain)

    print("MX:")
    c.check("@", f"10 {MAIL_TARGET}", domain, "MX")

    print("SRV:")
    c.check("_jmap._tcp", f"0 1 443 {MAIL_TARGET}", f"_jmap._tcp.{domain}", "SRV")
    c.check("_caldavs._tcp", f"0 1 443 {MAIL_TARGET}", f"_caldavs._tcp.{domain}", "SRV")
    c.check("_carddavs._tcp", f"0 1 443 {MAIL_TARGET}", f"_carddavs._tcp.{domain}", "SRV")
    c.check("_imaps._tcp", f"0 1 993 {MAIL_TARGET}", f"_imaps._tcp.{domain}", "SRV")
    c.check("_submission._tcp", f"0 1 587 {MAIL_TARGET}", f"_submission._tcp.{domain}", "SRV")

    print("TXT:")
    c.check("@ (SPF)", "v=spf1 include:spf.thundermail.com -all", domain, "TXT")
    c.check("_mta-sts", "v=STSv1;", f"_mta-sts.{domain}", "TXT")
    c.check("_smtp._tls", "v=TLSRPTv1;", f"_smtp._tls.{domain}", "TXT")
    c.check("_dmarc", "v=DMARC1;", f"_dmarc.{domain}", "TXT")

    print("CNAME (DKIM):")
    c.check("tm1._domainkey", f"tm1.{domain}.dkim.thunderhosted.com", f"tm1._domainkey.{domain}", "CNAME")
    c.check("tm2._domainkey", f"tm2.{domain}.dkim.thunderhosted.com", f"tm2._domainkey.{domain}", "CNAME")
    c.check("tm3._domainkey", f"tm3.{domain}.dkim.thunderhosted.com", f"tm3._domainkey.{domain}", "CNAME")

    print(f"\nResult: {c.passed} passed, {c.failed} failed.")
    return 0 if c.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
