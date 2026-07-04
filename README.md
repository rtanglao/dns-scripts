> We require all those who participate in this repo to agree and adhere to the
> [Mozilla Community Participation Guidelines](https://www.mozilla.org/about/governance/policies/participation/).

# dns-scripts

Small utilities for checking DNS records.

Licensed under [MPL-2.0](LICENSE).

## Thundermail DNS checker — web version

**<https://thunderbird.github.io/dns-scripts/>**

The same checks as the `verify_thundermail_dns.py` CLI below, but from a web
browser: enter a domain, optionally pick your DNS provider, and get pass/fail per
record plus exactly what to enter for any that are missing. All lookups run
client-side via DNS-over-HTTPS (Cloudflare or Google) — no server, nothing stored.

Run it locally with any static file server:

```sh
python3 -m http.server 8000   # then open http://localhost:8000/
```

> **Single source of truth:** the record set, value templates, and per-provider
> remediation strings live in [`records.json`](records.json), which is read by
> *both* the CLI and the web page (`index.html` + `app.js`). Add a record or a
> provider there once and both front-ends pick it up.

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
safe to use in scripts or CI. It queries `1.1.1.1` by default (override with
`--resolver` or the `DNS_RESOLVER` environment variable) to avoid stale local
caches. The resolver accepts an IP address or a hostname — e.g. point it at an
authoritative nameserver to bypass public-resolver caching entirely:

```sh
uv run verify_thundermail_dns.py glamrocnamecheap.com --resolver dns1.registrar-servers.com
```

### Fixing failures

Pass `--provider` to print, for each **failing** record, exactly what to enter in
that DNS provider's control panel — including provider-specific quirks such as how
the Host/Name field is written. Supported: `namecheap`, `squarespace`, `generic`.

```sh
uv run verify_thundermail_dns.py glamrocnamecheap.com --provider namecheap
```

For example, a missing DKIM CNAME prints:

```
• CNAME tm1._domainkey
  Namecheap → Advanced DNS → Add New Record → CNAME Record:
      Host:  tm1._domainkey
      Value: tm1.glamrocnamecheap.com.dkim.thunderhosted.com   (no trailing dot)
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
