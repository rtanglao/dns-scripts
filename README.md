> We require all those who participate in this repo to agree and adhere to the
> [Mozilla Community Participation Guidelines](https://www.mozilla.org/about/governance/policies/participation/).

# dns-scripts

Small utilities for checking DNS records.

Licensed under [MPL-2.0](LICENSE).

## Setup

Managed with [`uv`](https://docs.astral.sh/uv/):

```sh
uv sync
```

## verify_thundermail_dns.py

Verifies that a domain's DNS is configured for [Thundermail](https://thundermail.com):
the MX record, the JMAP/CalDAV/CardDAV/IMAPS/submission SRV records, the SPF /
MTA-STS / TLSRPT / DMARC TXT records, and the three DKIM CNAMEs.

```sh
uv run verify_thundermail_dns.py glamrocnamecheap.com
```

Exit status is `0` only when every expected record is present and correct, so it's
safe to use in scripts or CI. It queries `1.1.1.1` by default (override with the
`DNS_RESOLVER` environment variable) to avoid stale local caches. `DNS_RESOLVER`
accepts an IP address or a hostname — e.g. point it at an authoritative nameserver
to bypass public-resolver caching entirely:

```sh
DNS_RESOLVER=dns1.registrar-servers.com uv run verify_thundermail_dns.py glamrocnamecheap.com
```

### Example

```
Verifying Thundermail DNS for glamrocnamecheap.com (resolver 1.1.1.1)

MX:
  OK   @                                              10 mail.thundermail.com
SRV:
  OK   _jmap._tcp                                     0 1 443 mail.thundermail.com
  ...

Result: 13 passed, 0 failed.
```
