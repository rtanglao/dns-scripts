# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Purpose

`dns-scripts` verifies that a domain's DNS matches the **Thundermail**
(thundermail.com) email setup and, when records are missing/wrong, prints exactly
what to enter in a given DNS provider's control panel. It ships as **two
front-ends over one data file**:

- **CLI** — `verify_thundermail_dns.py` (Python, run via `uv`).
- **Web** — `index.html` + `app.js`, a static page that does all lookups in the
  browser via DNS-over-HTTPS. Hosted on GitHub Pages:
  **https://thunderbird.github.io/dns-scripts/**

The checked set is 13 records: 1 MX, 5 SRV (jmap/caldavs/carddavs/imaps/submission),
4 TXT (SPF / MTA-STS / TLSRPT / DMARC), 3 DKIM CNAMEs.

## Core architecture & crucial decisions

- **Single source of truth = `records.json`.** It holds the record set,
  `value_templates` (how each type's expected/full value string is built), and the
  per-provider remediation strings (`namecheap`, `squarespace`, `generic`). BOTH
  front-ends read it, so they can never drift. **Add a record or a provider once in
  `records.json` and both the CLI and the web app pick it up** — do not hardcode
  records/strings in the Python or JS.
- **Each front-end keeps only a tiny interpreter** (~20 lines): an `interpolate`
  (`{field}` token substitution), a `resolve_record`/`resolveRecord` (fills
  `{domain}`, computes `qname`/`fqdn`), and one platform-specific DNS-query
  function — dnspython (CLI) vs a DoH `fetch` (web). These are intentionally
  duplicated in Python and JS; keep them in sync. The **hostname-validation regex**
  is likewise duplicated in both — keep it identical.
- **Interpolation contract (both languages, must match):** substitute `{domain}`
  into every string field first; then `{field}` tokens in templates resolve against
  the concrete record. `re.sub`/`String.replace` use a **function** replacement so
  values are inserted literally (no second pass).
- **Web lookups use public DoH** (Cloudflare `cloudflare-dns.com/dns-query` with
  `accept: application/dns-json`, or Google `dns.google/resolve`). Public resolvers
  cache negative answers, so a freshly-added record can lag; the **CLI can query an
  authoritative NS directly** to bypass: `--resolver dns1.registrar-servers.com`.
- **Provider field conventions were verified against each provider's docs, not
  guessed** (e.g. Namecheap splits SRV into Host/Priority/Weight/Port/Target;
  Squarespace uses Name + a separate Priority + `Data` = "weight port target").
  Provider menu wording may drift — re-verify if a user reports it's off.

## Security posture

Reviewed; no exploitable injection/XSS/RCE. Defense-in-depth already in place —
preserve it when editing:

- **Web renders only via `textContent`** (never `innerHTML`) and builds DoH URLs
  with `encodeURIComponent`. A **CSP `<meta>`** locks `script-src 'self'` and
  `connect-src` to the two DoH hosts + self. Don't introduce inline scripts,
  `eval`, or `innerHTML` (they'd need CSP changes and reopen XSS).
- **CLI** escapes control/terminal bytes from DNS-derived output (`sanitize`),
  validates the domain against a hostname regex before any lookup (exit 2 on
  invalid), and caps displayed answer length.
- `--resolver` / `DNS_RESOLVER` are trusted (operator-controlled), out of scope.

## Commands

```sh
uv sync                                   # one-time / after dep changes

# CLI
uv run verify_thundermail_dns.py <domain>
uv run verify_thundermail_dns.py glamrocnamecheap.com --provider namecheap
uv run verify_thundermail_dns.py <domain> --resolver dns1.registrar-servers.com

# Web (static — any file server)
python3 -m http.server 8000               # then open http://localhost:8000/
```

Exit status is `0` only when all 13 records are present and correct.

## Testing

- **CLI regression:** normal-input output should stay byte-identical across
  refactors. Capture `glamrocnamecheap.com` (expect 13/13, exit 0) and
  `example.com --provider namecheap|squarespace|generic` before a change, then
  `diff` after. Also test invalid/malicious domains → rejected with exit 2.
- **Web headless (Playwright):** this repo has no Playwright dependency; run it
  from an env that does. Serve the site, then drive it. **The CSP (`script-src
  'self'`, no `unsafe-eval`) blocks Playwright's `page.wait_for_function`** — poll
  `page.inner_text('#summary')` in a loop instead. Confirm no console errors and no
  CSP violations (that verifies DoH + `records.json` requests aren't blocked).

## Deployment

GitHub Pages, source = `main` branch root, at
`https://thunderbird.github.io/dns-scripts/`. GitHub Pages can't set HTTP headers,
so the CSP is delivered as a `<meta http-equiv>` tag in `index.html`.

## License & contribution

MPL-2.0. **All source files carry the MPL header** (Python after the shebang, HTML
in an opening comment, JS at the top) — add it to every new file. Contributors
follow the [Mozilla Community Participation Guidelines](https://www.mozilla.org/about/governance/policies/participation/).
