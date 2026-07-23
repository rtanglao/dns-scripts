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
  per-provider remediation strings (`namecheap`, `squarespace`, `cosmotown`,
  `generic`). BOTH
  front-ends read it, so they can never drift. **Add a record or a provider once in
  `records.json` and both the CLI and the web app pick it up** — do not hardcode
  records/strings in the Python or JS.
- **Each front-end keeps only a tiny interpreter** (~20 lines): an `interpolate`
  (`{field}` token substitution), a `resolve_record`/`resolveRecord` (fills
  `{domain}`, computes `qname`/`fqdn`, and `subhost` = the host label but empty at
  the apex, for panels like Cosmotown whose Host field is left blank — not `@` —
  for the root domain), and one platform-specific DNS-query
  function — dnspython (CLI) vs a DoH `fetch` (web). These are intentionally
  duplicated in Python and JS; keep them in sync. The **hostname-validation regex**
  is likewise duplicated in both — keep it identical.
- **SRV-label split tokens (`{service}`/`{protocol}`/`{srvhost}`).** The interpreter
  also splits the SRV host label on `.`: `{service}` = first label (`_jmap`),
  `{protocol}` = second (`_tcp`), `{srvhost}` = the rest or `@` (always `@` for our
  records, which live at the apex). These exist **only for GoDaddy**, whose add-record
  form breaks SRV into separate Service/Protocol/Name fields — every other provider
  keeps the whole `_jmap._tcp` in one Host field. They're computed for all records but
  only referenced by the split-SRV templates (`godaddy`, `ionos`, `hover`). There's a
  sibling token **`{srvsubhost}`** = the same "rest" label but **blank at the apex
  instead of `@`** (mirroring how `{subhost}` relates to `{host}`); it exists only for
  Hover, whose SRV form leaves the optional Subdomain field empty for the root. Like the
  rest of the interpreter, the split is **duplicated in both Python and JS — keep it
  identical.**
- **Interpolation contract (both languages, must match):** substitute `{domain}`
  into every string field first; then `{field}` tokens in templates resolve against
  the concrete record. `re.sub`/`String.replace` use a **function** replacement so
  values are inserted literally (no second pass).
- **Web lookups use public DoH** (Cloudflare `cloudflare-dns.com/dns-query` with
  `accept: application/dns-json`, or Google `dns.google/resolve`). Public resolvers
  cache negative answers, so a freshly-added record can lag; the **CLI can query an
  authoritative NS directly** to bypass: `--resolver dns1.registrar-servers.com`
  (Namecheap). **Check the domain's actual delegation first** (`dig NS <domain>`) —
  Cosmotown, for example, runs two nameserver families: `ns1..ns4.cosmotown.com`
  (Cloudflare-fronted) and `ndns1`/`ndns2.cosmotown.com` (AWS). A domain lives on
  only one; querying the wrong one returns `REFUSED` (shows up as `<empty>` for
  every record). Cosmotown example: `--resolver ndns1.cosmotown.com`
  ([Cosmotown: nameservers](https://cosmotown.zendesk.com/hc/en-us/articles/214830046-How-to-change-your-Nameservers-What-are-Cosmotown-s-Nameservers)).
  Bunny DNS delegates to `kiki.bunny.net` / `coco.bunny.net`, so
  `--resolver kiki.bunny.net` queries it authoritatively (verified against the live
  `soylent.red` zone — 13/13).
- **Provider field conventions were verified against each provider's docs, not
  guessed** (e.g. Namecheap splits SRV into Host/Priority/Weight/Port/Target;
  Squarespace uses Name + a separate Priority + `Data` = "weight port target").
  Provider menu wording may drift — re-verify if a user reports it's off.
  `cosmotown` was verified against a live panel (dexterica.com). Its quirks:
  records are grouped into per-type sections each with its own `+ Quick Add`
  (so there's no Type field); columns are `Priority`/`Host`/`Points to` (MX),
  `Host`/`Points to` (CNAME), `Host`/`TXT Value` (TXT); MX Host is left blank for
  the root and the panel auto-fills the domain; the CNAME `Points to` is stored
  with a trailing dot automatically; TXT values are wrapped in quotes by the panel
  and are case-sensitive; and **there is no SRV section at all** — the SRV block
  routes the user to Cosmotown support instead. Docs:
  [changing/saving DNS records](https://cosmotown.zendesk.com/hc/en-us/articles/214829926-How-to-change-and-save-your-DNS-Records),
  [adding a host name](https://cosmotown.zendesk.com/hc/en-us/articles/214830006-How-to-add-a-Host-Name-to-your-Domain-name-s-DNS),
  [updating the MX record](https://cosmotown.zendesk.com/hc/en-us/articles/214830106-How-to-update-the-MX-Record)
  (Zendesk is behind Cloudflare, so these need a real browser — automated fetches 403).
  `bunny` was verified against bunny.net's
  [DNS records docs](https://docs.bunny.net/docs/dns-records). Its add-record dialog
  is a single form (`Hostname`/`Type`/`TTL`/`Value`, Type chosen from a dropdown):
  `Hostname` is left **empty** for the root (never `@`), and there is **one `Value`
  field with no separate Priority/Weight/Port**, so MX and SRV put the whole record
  string in `Value` (the `{match}` template — e.g. `10 mail.thundermail.com`). The
  record list's `Weight` column is bunny's A/AAAA load-balancing "Routing Weight",
  not the SRV weight, so it's irrelevant here.
  `godaddy` (**UNVERIFIED** — from GoDaddy's help docs + a screenshot of the live SRV
  add-form, not yet confirmed end-to-end; headers carry an `UNVERIFIED —` prefix, drop
  them once validated on a live GoDaddy-hosted domain). A single Add-record form with a
  Type dropdown (like bunny). Apex `Name` is written as **`@`** (`{host}`), *not* blank
  like bunny/cosmotown. MX has a separate `Priority`; SPF is a plain `TXT`. The
  distinctive quirk: the **SRV form splits the record into separate `Service`
  (`_jmap`) + `Protocol` (`_tcp`) + `Name` (`@`) fields** — the reason the
  `{service}`/`{protocol}`/`{srvhost}` tokens exist. Note this is a *UI-layout*
  difference only: contrast Spaceship, whose *import preview* also displayed a split
  but whose API stores SRV as one combined `name` (`_jmap._tcp`) — so `spaceship` ships
  the combined form and only `godaddy` splits it. Docs: GoDaddy Help CA articles for
  [MX](https://www.godaddy.com/en-ca/help/add-an-mx-record-19234),
  [TXT](https://www.godaddy.com/en-ca/help/add-a-txt-record-19232),
  [SPF](https://www.godaddy.com/en-ca/help/add-an-spf-record-19218),
  [CNAME](https://www.godaddy.com/en-ca/help/add-a-cname-record-19236),
  [SRV](https://www.godaddy.com/en-ca/help/add-an-srv-record-19216).
  `hover` (**UNVERIFIED** — the SRV field layout is confirmed from a screenshot of the
  live *Edit DNS Record* form; MX/TXT/CNAME field labels come from Hover's
  [Managing DNS Records at Hover](https://support.hover.com/) docs, not a live add-record
  screenshot; drop the `UNVERIFIED —` prefixes once confirmed end-to-end — `mitchener.ca`
  is the verify target, hosted on `ns1`/`ns2.hover.com`). A single **Add a record** form
  with a Type dropdown (like bunny/godaddy). MX and TXT write the apex host as **`@`**
  (`{host}`, per Hover's docs). The distinctive quirk: like GoDaddy/IONOS, the **SRV form
  splits the label into separate `Service` (`_jmap`) + `Protocol` (`_tcp`) fields** — but
  its optional `Subdomain` field is left **blank** for the apex (`{srvsubhost}`, *not*
  `@`; the panel shows your domain beside the empty box). MX uses `Mail Server` for the
  target, TXT uses `Content`, CNAME uses `Target Name` (no trailing dot); Hover can't set
  a CNAME on the root, but every DKIM CNAME is on a subdomain so that's a non-issue.
  `digitalocean` (**UNVERIFIED** — the **SRV** field layout is confirmed from a screenshot
  of the live *Create a record* dialog; MX/TXT/CNAME labels come from DigitalOcean's
  [manage-records docs](https://docs.digitalocean.com/products/networking/dns/how-to/manage-records/),
  not a live add-record screenshot; drop the `UNVERIFIED —` prefixes once confirmed
  end-to-end — `emilio.me` is the verify target, hosted on `ns1`/`ns2`/`ns3.digitalocean.com`).
  A single **Create a record** dialog with a Record Type dropdown (like bunny/godaddy/hover).
  Apex host is **`@`** (`{host}`) for MX/TXT, *not* blank. Unlike GoDaddy/IONOS/Hover it
  keeps the whole `_service._protocol` label in **one** `Hostname` field — so SRV uses
  `{host}`, not the split `{service}`/`{protocol}` tokens. The distinctive quirk: **any
  target entered without a trailing dot gets your domain appended** (the SRV *Will direct
  to* doc spells this out), so MX/SRV/CNAME targets are emitted as `{target}.` with the dot
  (like `ovh`). This is confirmed live: `emilio.me`'s SRV targets were entered without the
  dot and resolve as `mail.thundermail.com.emilio.me` — so its five SRV records are actually
  broken (and, separately, the substring-match checker falsely reports them OK — see the
  matching bug). MX field is `Mail provider's mail server`, TXT is `TXT Value`, CNAME is
  `Is an alias of`; SPF/DKIM are plain TXT per the docs (DKIM here is a CNAME).
  `porkbun` (**UNVERIFIED** — MX/TXT/CNAME field layout from Porkbun's KB
  [article 231](https://kb.porkbun.com/article/231-how-to-add-dns-records-on-porkbun)
  and SRV from [article 109](https://kb.porkbun.com/article/109-how-to-create-an-srv-record)
  (screenshots), not confirmed end-to-end on a live panel; drop the `UNVERIFIED —` prefixes
  once confirmed — `wrportal.net` is the verify target, hosted on
  `curitiba`/`fortaleza`/`maceio`/`salvador.ns.porkbun.com`, so
  `--resolver curitiba.ns.porkbun.com` queries it authoritatively). A single **Add Record**
  dialog with a Type dropdown (like bunny/godaddy/hover/digitalocean); Porkbun DNS is
  Cloudflare-backed. Apex host is left **blank** (`{subhost}`), *not* `@` — the
  bunny/cosmotown/ovh pattern. Like DigitalOcean it keeps the whole `_service._protocol`
  label in **one** `Host` field (SRV uses `{host}`, not the split tokens). MX and SRV show a
  separate **Priority** field, and the SRV **Answer** field packs Weight/Port/Target on one
  line (`{value}`, the squarespace-style split). Unlike `ovh`/`digitalocean`, targets are
  stored **verbatim with no trailing dot** — confirmed live on `wrportal.net` (its MX and
  DKIM CNAME targets came back unappended), so MX/SRV/CNAME emit plain `{target}` like
  `bunny`. Value field is labelled contextually in the UI (`IPv4 Address`/`Target`/`Answer`);
  we emit `Answer` for MX/SRV/TXT and `Target` for CNAME. SPF/DKIM are plain TXT (DKIM is a
  CNAME here).
- **Bookmarkable web URLs (web-only).** `app.js` mirrors the form state (domain /
  provider / resolver / fixformat) into the query string via `history.replaceState`,
  and on load repopulates the fields and auto-runs when a `domain` is present. This is
  the **one intentionally web-only feature** — the CLI has no URL, so the
  Python/JS-in-sync rule does not apply. Untrusted params are validated against the
  known option sets before use and only ever assigned to `input.value`/`select.value`
  (never `innerHTML`); the domain still passes the hostname regex before any lookup —
  so it adds no XSS surface and needs **no CSP change**.

## Security posture

Reviewed; no exploitable injection/XSS/RCE. Defense-in-depth already in place —
preserve it when editing:

- **Web renders only via `textContent`** (never `innerHTML`) and builds DoH URLs
  with `encodeURIComponent`. A **CSP `<meta>`** locks `script-src 'self'` and
  `connect-src` to the two DoH hosts + self. Don't introduce inline scripts,
  `eval`, or `innerHTML` (they'd need CSP changes and reopen XSS). URL query params
  (the bookmarkable-state feature) are untrusted input — validate against known
  option sets and assign only to `input.value`/`select.value`, never `innerHTML`.
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

- **Automated suite (`tests/`, stdlib `unittest`, no network):** run with
  `uv run python -m unittest discover -s tests -t . -v` (also runs in CI via
  `.github/workflows/test.yml` on push/PR). `test_verify.py` covers the pure
  interpreter (matching incl. the #10 exact-vs-contains regression, token
  resolution, provider rendering) and lints `records.json` (every provider covers
  all four types; every field template interpolates with no unknown/leftover
  token; each `value_templates.<TYPE>` has a valid `match_mode`). `test_parity.py`
  enforces the **Python↔JS sync rule**: it runs `tests/fixtures/parity_cases.json`
  through both the Python functions and a Node harness (`tests/parity/run_js.mjs`,
  which loads `app.js` in a `vm` sandbox) and asserts identical results — so when
  you change the interpreter in one language, update the other or this test fails.
  Add a fixture case whenever you add an interpreter token or `match_mode`.
  ⚠️ **Harness fragility (by design):** `run_js.mjs` relies on `app.js`'s *only*
  top-level side effect being the trailing `loadConfig().then(...)`, which it
  neutralizes by stubbing `fetch` to stay pending (so the DOM-touching callback
  never fires). If you add **new top-level (module-load-time) code to `app.js`**
  that touches `document`/`window`/`location`/etc., the sandbox stubs in
  `run_js.mjs` must be extended to match, or the parity test errors at load. This
  is intentional pressure to keep `app.js`'s pure interpreter functions free of
  load-time DOM coupling — but it means "just added a line to app.js" can surface
  as a parity-harness failure rather than an obvious app bug; check `run_js.mjs`'s
  stubs first in that case.
- **CLI regression:** normal-input output should stay byte-identical across
  refactors. Capture `glamrocnamecheap.com` (expect 13/13, exit 0) and
  `example.com --provider namecheap|squarespace|cosmotown|generic` before a change, then
  `diff` after. Also test invalid/malicious domains → rejected with exit 2.
- **Fix layout:** `--provider` fixes default to a compact per-type table (one
  column per provider field, one row per failing record); `--fix-format long`
  gives the older one-labelled-block-per-record layout. The web app mirrors this
  with the "Fix format" selector (Table/Detailed). Both are driven off the same
  `providers.<name>.<TYPE>.fields` in `records.json` — keep the two renderers in
  sync. When capturing a CLI baseline, pin `--fix-format` so the diff is stable.
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
