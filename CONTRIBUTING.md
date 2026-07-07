# Contributing

> We require all those who participate in this repo to agree and adhere to the
> [Mozilla Community Participation Guidelines](https://www.mozilla.org/about/governance/policies/participation/).

Licensed under [MPL-2.0](LICENSE). **Every source file carries the MPL header**
(Python after the shebang, HTML in an opening comment, JS at the top) — add it to
any new source file. Markdown docs like this one don't need it.

For architecture and testing details, see [`README.md`](README.md) and
[`CLAUDE.md`](CLAUDE.md). The short version: the record set, value templates, and
per-provider remediation strings all live in **`records.json`**, read verbatim by
both front-ends (the `verify_thundermail_dns.py` CLI and the `index.html`/`app.js`
web app), so the two can never drift.

## Adding or fixing a DNS provider

A provider is pure data — no code changes. Add a block under `providers` in
`records.json` and both front-ends pick it up automatically (the CLI `--provider`
choice and the web "Show fixes for" dropdown). Give it one entry per record type
(`MX`, `SRV`, `TXT`, `CNAME`), each with a `header` (the instruction line) and
`fields` (a list of `[label, template]` pairs). Templates interpolate the same
tokens the CLI/JS expose on a record — `{host}`, `{subhost}` (host label, blank at
the apex), `{target}`, `{priority}`, `{weight}`, `{port}`, `{value}`, `{match}`,
`{fqdn}`, `{qname}`, `{domain}`.

### Verify field conventions against the *actual panel* — not an automated fetch

This is the important one, and it's why this file exists.

**Provider field labels and quirks must be confirmed from the live control panel,
not guessed and not scraped by an automated tool.** Two reasons:

1. **Many provider help sites can't be fetched programmatically.** Cosmotown's
   docs, for example, sit behind Cloudflare's bot challenge and return **HTTP 403**
   to `curl`, `WebFetch`, and headless browsers alike (the Wayback Machine has no
   snapshots either). Don't burn time fighting the challenge.
2. **Docs drift from the UI, and the UI is the source of truth.** For Cosmotown the
   live panel contradicted the docs in ways that mattered: records are grouped into
   per-type sections (so there's *no* "Type" field), the value column is labelled
   `Points to` / `TXT Value` (not "Value"), the root Host is left **blank** (never
   `@`), the CNAME target is stored with a trailing dot automatically, and there's
   **no SRV section at all**. A screenshot caught all of that; the docs alone would
   have led us wrong.

**Best source, in order:** a **screenshot of the live panel** (the record-list view
*and* an "add record" form — they reveal column labels, how the root/apex host is
written, and trailing-dot handling) → reading the docs in a **real browser** →
last resort, the provider's published docs quoted verbatim. When you land the
provider, cite the docs you used (see the Cosmotown links in `README.md`).

### Before you open a PR

- Run the CLI against a domain and eyeball both fix layouts:
  `--provider <name>` (compact table, default) and `--provider <name> --fix-format long`.
- Serve the web app (`python3 -m http.server 8000`), pick the provider, and confirm
  the same output renders with no console/CSP errors.
- Keep the CLI and web renderers in sync — they intentionally duplicate a tiny
  interpreter over `records.json`. See the regression and headless-testing notes in
  [`CLAUDE.md`](CLAUDE.md#testing).
