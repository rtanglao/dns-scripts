# dns-scripts

Small utilities for checking DNS records.

## verify-thundermail-dns.sh

Verifies that a domain's DNS is configured for [Thundermail](https://thundermail.com):
the MX record, the JMAP/CalDAV/CardDAV/IMAPS/submission SRV records, the SPF /
MTA-STS / TLSRPT / DMARC TXT records, and the three DKIM CNAMEs.

```sh
./verify-thundermail-dns.sh glamrocnamecheap.com
```

Exit status is `0` only when every expected record is present and correct, so it's
safe to use in scripts or CI. It queries `1.1.1.1` by default (override with
`DNS_RESOLVER`) to avoid stale local caches.

Requires `dig` (`bind-tools` on macOS/Homebrew, `dnsutils` on Debian/Ubuntu).

### Example

```
Verifying Thundermail DNS for glamrocnamecheap.com (resolver 1.1.1.1)

MX:
  OK   @                                              10 mail.thundermail.com
SRV:
  OK   _jmap._tcp                                     0 1 443 mail.thundermail.com
  ...

Result: 15 passed, 0 failed.
```
