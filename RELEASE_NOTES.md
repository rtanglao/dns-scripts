# Release notes

Chronological record of provider-remediation support added to `dns-scripts`. Each
provider is pure data in [`records.json`](records.json); both front-ends (the
`verify_thundermail_dns.py` CLI and the `index.html`/`app.js` web app) pick it up
automatically. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the onboarding workflow
and the verification bar every provider is held to.

## Providers

| Provider      | Added      | Verification                                                                 |
| ------------- | ---------- | ---------------------------------------------------------------------------- |
| `namecheap`   | 2026-07-02 | Field conventions verified against Namecheap's docs.                         |
| `squarespace` | 2026-07-02 | Field conventions verified against Squarespace's docs.                       |
| `generic`     | 2026-07-02 | Provider-agnostic FQDN/value fallback — nothing panel-specific to verify.    |
| `cosmotown`   | 2026-07-07 | Verified against a live panel (dexterica.com); quirks confirmed from a record-list screenshot. |
| `bunny`       | 2026-07-13 | Verified against bunny.net's official docs (docs.bunny.net/docs/dns-records). |

## Notes

### `bunny` (bunny.net)

Added 2026-07-13. First drafted from a record-list screenshot (the `soylent.red`
zone), then **corrected and verified** the same day against bunny.net's official
docs ([DNS records](https://docs.bunny.net/docs/dns-records)). The confirmed
conventions:

- The add-record dialog is a **single form** with a **Type** dropdown (not per-type
  sections like Cosmotown) and fields **Hostname / Type / TTL / Value**.
- **Hostname** is left **empty for the root domain** (the `subhost` pattern) — never
  `@`; bunny lists apex records under the full domain name.
- There is **one Value field with no separate Priority / Weight / Port fields**, so
  MX and SRV put the whole record string in Value (`{match}`) — e.g. MX
  `10 mail.thundermail.com`, SRV `0 1 443 mail.thundermail.com`. The record-list
  screenshot corroborated this (MX displayed as `10 mail.thundermail.com`).
- The record list's **Weight** column is bunny's A/AAAA load-balancing "Routing
  Weight" (0-100, under Advanced Settings), **not** the SRV weight — so it does not
  factor into any of the Thundermail records.

Corrections made from the initial screenshot-only draft: the field is **Hostname**
(not "Name"); MX/SRV use a single **Value** (not separate Priority/Weight/Port);
dropped the unverified CNAME "no trailing dot" note.
