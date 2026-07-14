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
| `bunny`       | 2026-07-13 | **Untested.** Inferred from a record-list screenshot (soylent.red) only.     |

## Notes

### `bunny` (bunny.net) — untested

Added 2026-07-13 from a bunny.net DNS **record-list** screenshot (the `soylent.red`
zone) — CONTRIBUTING artifact type 2, not the higher-priority "add / edit record
form" (type 1). What the list confirmed:

- Columns are **TYPE / NAME / VALUE / WEIGHT / TTL**.
- Subdomain records show just the label in NAME (`mta-sts`, `tm1._domainkey`,
  `_dmarc`, …); true apex records (MX and SPF TXT) display the **full domain**,
  which we read as the Name field being left **blank** at the root (the `subhost`
  pattern, like Cosmotown) rather than `@`.

Still **unverified** against a live add-record form:

- The SRV field labels and order (we assumed Priority / Weight / Port / Value).
- Whether the CNAME `Value` should carry a trailing dot (we noted "no trailing dot").
- Whether the add-record dialog has a single Type dropdown (assumed) vs. per-type
  sections like Cosmotown.

To promote `bunny` to verified: capture the add / edit record form with the record
-type dropdown expanded, confirm the four field sets, then drop the "untested" note
here and in [`README.md`](README.md).
