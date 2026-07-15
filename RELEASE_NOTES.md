# Release notes

Chronological record of provider-remediation support added to `dns-scripts`. Each
provider is pure data in [`records.json`](records.json); both front-ends (the
`verify_thundermail_dns.py` CLI and the `index.html`/`app.js` web app) pick it up
automatically. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the onboarding workflow
and the verification bar every provider is held to.

## ⚠️ Pending verification

**`spaceship` is unverified.** To promote it (do this when you have a live Spaceship
panel open):

1. Open the panel and click **+ Add record** for one record of each type
   (MX / SRV / TXT / CNAME) — the *manual* form, not the zone-import preview.
2. Confirm three things:
   - The exact field labels in the add form (is it `Host` or `Hostname`? etc.).
   - **SRV host** — does the form want it as one field (`_caldavs._tcp`, what we
     ship) or split into service + protocol (`_caldavs` + `_tcp`, as the import
     preview showed)?
   - Whether CNAME/MX targets need a trailing dot (the import preview stored one).
3. Fix `records.json` if anything differs, then remove the `UNVERIFIED —` prefixes
   from the four `spaceship` headers, and delete the unverified notes in
   [`README.md`](README.md) and the `spaceship` section below.

Details and reasoning are in the [`spaceship` notes](#spaceship-spaceshipcom--unverified).

**`godaddy` is unverified.** To promote it (do this when you have a live GoDaddy
panel open):

1. Open **DNS → DNS Records → Add New Record** and pick each Type
   (MX / SRV / TXT / CNAME) in turn.
2. Confirm three things:
   - The exact field labels in the add form (the SRV form screenshot shows
     `Type / Service / Protocol / Name / Value / Priority / Weight / Port`; check
     the MX/TXT/CNAME forms match `Type / Name / Priority / Value` etc.).
   - **Apex Name** is entered as `@` (what we ship), not left blank.
   - Whether CNAME/MX/SRV targets (Value) need a trailing dot.
3. Fix `records.json` if anything differs, then remove the `UNVERIFIED —` prefixes
   from the four `godaddy` headers, and delete the unverified notes in
   [`README.md`](README.md) and the `godaddy` section below.

Details and reasoning are in the [`godaddy` notes](#godaddy-godaddycom--unverified).

## Providers

| Provider      | Added      | Verification                                                                 |
| ------------- | ---------- | ---------------------------------------------------------------------------- |
| `namecheap`   | 2026-07-02 | Field conventions verified against Namecheap's docs.                         |
| `squarespace` | 2026-07-02 | Field conventions verified against Squarespace's docs.                       |
| `generic`     | 2026-07-02 | Provider-agnostic FQDN/value fallback — nothing panel-specific to verify.    |
| `cosmotown`   | 2026-07-07 | Verified against a live panel (dexterica.com); quirks confirmed from a record-list screenshot. |
| `bunny`       | 2026-07-13 | Verified against bunny.net's official docs (docs.bunny.net/docs/dns-records). |
| `spaceship`   | 2026-07-13 | **Unverified.** Inferred from a zone-import screenshot + Spaceship's Spacemail docs. |
| `godaddy`     | 2026-07-14 | **Unverified.** From GoDaddy's help docs + a live SRV add-form screenshot; not confirmed end-to-end. |

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

**Live validation (2026-07-13):** ran the CLI against the real bunny.net-hosted
`soylent.red` (delegated to `kiki`/`coco.bunny.net`) → **13/13 passed, exit 0**.
Driven by Zendesk ticket [6750](https://tbpro.zendesk.com/agent/tickets/6750).
Every value bunny.net serves matches the expected strings byte-for-byte, including
`MX 10 mail.thundermail.com` and `SRV 0 1 443 mail.thundermail.com` — confirming the
single-`Value`-field (`{match}`) remediation produces exactly what the panel stores.

### `spaceship` (spaceship.com) — unverified

Added 2026-07-13 for Zendesk ticket
[6672](https://tbpro.zendesk.com/agent/tickets/6672). Marked **unverified** because
the two sources only partly cover it:

- A **zone-import preview** screenshot from the real `dexterica.com` zone
  (CONTRIBUTING artifact type 2, and specifically the *import* view — not the
  higher-priority manual add-record form, type 1).
- Spaceship's official docs
  ([Required DNS records for Spacemail](https://www.spaceship.com/knowledgebase/spacemail-dns-records-third-party-domain/)),
  which document **Spacemail's own** records (`mx1.spacemail.com`, …), a *different*
  record set — so they confirm the panel's column labels but not the Thundermail
  entries.

What the sources agree on and we encoded:

- Columns are **Host / Type / Value / TTL** (docs call Host "Hostname"); the panel
  auto-appends the domain to Host and uses **`@` for the root** (not blank).
- **MX** has a separate **Priority** field alongside the target Value.
- **SRV** breaks out **Priority / Weight / Port / Target** as separate fields.
- The provider headers themselves carry an `UNVERIFIED` prefix so CLI/web users see
  the caveat inline.

Still **unverified** against a live manual add-record form:

- Exact field labels in the *add* form (vs. the import preview).
- **SRV host**: the import view split it into `_caldavs` + `_tcp` (service +
  protocol) fields; we encoded the combined `_caldavs._tcp` (matching the docs'
  single `_autodiscover._tcp` hostname). Confirm which the add form expects.
- Whether CNAME/MX targets need a trailing dot (the import view showed them stored
  with one).

To promote to verified: capture the manual add-record form for one record of each
type, confirm the field sets, then drop the `UNVERIFIED` prefixes in `records.json`
and the note here and in [`README.md`](README.md).

### `godaddy` (godaddy.com) — unverified

Added 2026-07-14 for internal ticket 6850 (`6850_GODADDY_CUSTOM_DOMAIN`). Marked
**unverified**: the conventions come from GoDaddy's official help articles plus a
screenshot of the live **SRV** add-record form, but haven't been confirmed end-to-end
by adding all 13 records on a live GoDaddy-hosted domain. Sources:
[MX](https://www.godaddy.com/en-ca/help/add-an-mx-record-19234),
[TXT](https://www.godaddy.com/en-ca/help/add-a-txt-record-19232),
[SPF](https://www.godaddy.com/en-ca/help/add-an-spf-record-19218),
[CNAME](https://www.godaddy.com/en-ca/help/add-a-cname-record-19236),
[SRV](https://www.godaddy.com/en-ca/help/add-an-srv-record-19216).

What the docs + screenshot establish and we encoded:

- The add-record dialog is a **single form** with a **Type** dropdown (like `bunny`
  / `spaceship`, not per-type sections like Cosmotown). Path: **Domain Portfolio →
  domain → DNS → DNS Records → Add New Record**.
- **Name** is entered as **`@` for the root domain** (GoDaddy uses `@`, not a blank
  field — the `{host}` pattern, unlike bunny/cosmotown's blank apex).
- **MX** has a separate **Priority** field; **Value** is the mail host alone.
- **SRV** is the most decomposed of any provider: the form breaks the
  `_service._protocol` label into separate **Service** (`_jmap`) and **Protocol**
  (`_tcp`) fields, plus **Name** (`@` at the apex), **Value** (target), and separate
  **Priority / Weight / Port**. This is the first provider to need it, so it added
  `{service}` / `{protocol}` / `{srvhost}` tokens to the shared interpreter in
  **both** `verify_thundermail_dns.py` and `app.js` (derived by splitting the SRV
  host label on `.`; kept in sync per CLAUDE.md).
- **SPF** is added as a plain **TXT** record (GoDaddy's SPF help article is just a
  TXT with an SPF value), so it uses the TXT field set.
- The provider headers carry an `UNVERIFIED —` prefix so CLI/web users see the
  caveat inline.

Still **unverified** against a live end-to-end add: the exact MX/TXT/CNAME field
labels (only the SRV form was screenshotted), and whether any target Value needs a
trailing dot. To promote: add one record of each type on a live GoDaddy-hosted
domain, confirm 13/13 via `--resolver <the domain's GoDaddy authoritative NS>`, then
drop the `UNVERIFIED` prefixes in `records.json` and the notes here and in
[`README.md`](README.md).
