> We require all those who participate in this repo to agree and adhere to the
> [Mozilla Community Participation Guidelines](https://www.mozilla.org/about/governance/policies/participation/).

# dns-scripts

Small utilities for checking DNS records.

Licensed under [MPL-2.0](LICENSE). Contributing (especially **adding a DNS
provider**)? See [`CONTRIBUTING.md`](CONTRIBUTING.md).

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

Point it at whichever nameserver is actually authoritative for the domain — check
with `dig NS <domain>` first, since a registrar may run several nameserver sets and
querying the wrong one just returns empty answers. For example, a domain hosted on
Cosmotown's DNS is usually delegated to `ndns1.cosmotown.com` / `ndns2.cosmotown.com`
([Cosmotown: What are Cosmotown's nameservers?](https://cosmotown.zendesk.com/hc/en-us/articles/214830046-How-to-change-your-Nameservers-What-are-Cosmotown-s-Nameservers)):

```sh
uv run verify_thundermail_dns.py <domain> --resolver ndns1.cosmotown.com
```

A domain hosted on Bunny DNS is delegated to `kiki.bunny.net` / `coco.bunny.net`
([bunny.net: DNS records](https://docs.bunny.net/docs/dns-records)):

```sh
uv run verify_thundermail_dns.py <domain> --resolver kiki.bunny.net
```

### Fixing failures

Pass `--provider` to print, for each **failing** record, exactly what to enter in
that DNS provider's control panel — including provider-specific quirks such as how
the Host/Name field is written. Supported: `namecheap`, `squarespace`, `cosmotown`,
`bunny`, `spaceship`, `godaddy`, `ionos`, `generic`. bunny.net's add-record form has a single
**Value** field (no separate Priority/Weight/Port), so the `bunny` MX/SRV output puts
the whole record string in Value; the Hostname field is left empty for the root
([bunny.net: DNS records](https://docs.bunny.net/docs/dns-records)). **`spaceship`
is unverified** — its field conventions were inferred from a zone-import screenshot
and Spaceship's own Spacemail docs (a different record set), not confirmed against
the live manual add-record form, so its headers flag this and the SRV host handling
is uncertain (see [`RELEASE_NOTES.md`](RELEASE_NOTES.md)). **`godaddy` is also
unverified** — its field conventions come from GoDaddy's help docs plus a screenshot
of the live SRV add-record form, not yet confirmed end-to-end on a live GoDaddy-hosted
domain, so its headers flag this. GoDaddy is the one panel that splits the SRV
`_service._protocol` label into separate **Service** and **Protocol** fields
(the record Name is then `@` for the root). **`ionos` is also unverified** — its
field conventions come from IONOS's help docs plus a screenshot of the live SRV
add-record form, not yet confirmed end-to-end on a live IONOS-hosted domain, so its
headers flag this. IONOS also splits the SRV `_service._protocol` label, but its
Protocol is a `TCP`/`UDP`/`TLS` dropdown (hard-coded to `TCP`, since every checked
SRV record is `_tcp`), and its SRV form has both a **Host name** (record location)
and a separate **Points to** (target). Note that
Cosmotown's customer panel has no SRV section, so the five SRV
records can't be self-served — the `cosmotown` output routes you to Cosmotown support
for those. See Cosmotown's docs for
[changing/saving DNS records](https://cosmotown.zendesk.com/hc/en-us/articles/214829926-How-to-change-and-save-your-DNS-Records),
[adding a host name](https://cosmotown.zendesk.com/hc/en-us/articles/214830006-How-to-add-a-Host-Name-to-your-Domain-name-s-DNS),
and [updating the MX record](https://cosmotown.zendesk.com/hc/en-us/articles/214830106-How-to-update-the-MX-Record).

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
