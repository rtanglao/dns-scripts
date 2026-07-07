// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

// Browser twin of the logic in verify_thundermail_dns.py. Both front-ends read
// the same records.json, so the record set, value templates, and provider
// remediation strings live in exactly one place.

const TOKEN = /\{(\w+)\}/g;

// Hostname validation (kept in sync with the same regex in verify_thundermail_dns.py).
const HOSTNAME = /^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$/;

const MAX_VALUE = 300; // cap displayed answer length to avoid DOM bloat
const cap = (s) => (s.length <= MAX_VALUE ? s : s.slice(0, MAX_VALUE) + "…");

// Numeric DNS type codes, to keep only answers of the requested type (a DoH
// response can also carry CNAMEs from a resolution chain).
const TYPE_NUM = { A: 1, CNAME: 5, MX: 15, TXT: 16, SRV: 33 };

const RESOLVERS = {
  cloudflare: {
    url: (name, type) =>
      `https://cloudflare-dns.com/dns-query?name=${encodeURIComponent(name)}&type=${type}`,
    headers: { accept: "application/dns-json" },
  },
  google: {
    url: (name, type) =>
      `https://dns.google/resolve?name=${encodeURIComponent(name)}&type=${type}`,
    headers: {},
  },
};

// --- shared interpretation of records.json (mirrors the Python helpers) -------

function labelOf(rec) {
  return rec.label ?? rec.host;
}

function resolveRecord(rec, domain) {
  const host = rec.host;
  const ctx = {};
  for (const [k, v] of Object.entries(rec)) {
    ctx[k] = typeof v === "string" ? v.replaceAll("{domain}", domain) : v;
  }
  ctx.domain = domain;
  ctx.qname = host === "@" ? domain : `${host}.${domain}`;
  ctx.fqdn = host === "@" ? `${domain}.` : `${host}.${domain}.`;
  return ctx;
}

function interpolate(template, ctx) {
  return template.replace(TOKEN, (_, k) => String(ctx[k]));
}

function valueOf(ctx, cfg, key) {
  return interpolate(cfg.value_templates[ctx.type][key], ctx);
}

function renderFix(cfg, provider, ctx) {
  // Long form: header + labelled fields for a single record.
  const block = cfg.providers[provider][ctx.type];
  const width = Math.max(...block.fields.map(([lbl]) => lbl.length)) + 1;
  const lines = [block.header];
  for (const [lbl, tpl] of block.fields) {
    lines.push(`    ${(lbl + ":").padEnd(width)} ${interpolate(tpl, ctx)}`);
  }
  return lines;
}

// Compact form: provider header, then a table with one column per field and one
// row per failing record of the same type. Built from DOM nodes (textContent
// only) so it stays within the CSP — no innerHTML.
function fixTable(cfg, provider, rtype, ctxs) {
  const block = cfg.providers[provider][rtype];
  const wrap = el("div", "fix");
  wrap.appendChild(el("p", "fixhdr", block.header));
  const table = el("table", "fixtable");
  const htr = el("tr");
  for (const [lbl] of block.fields) htr.appendChild(el("th", null, lbl));
  table.appendChild(el("thead", null)).appendChild(htr);
  const tbody = el("tbody");
  for (const ctx of ctxs) {
    const tr = el("tr");
    for (const [, tpl] of block.fields) tr.appendChild(el("td", null, interpolate(tpl, ctx)));
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);
  return wrap;
}

// --- DNS query (the one genuinely platform-specific piece: DoH here) ----------

async function query(resolver, name, type) {
  const r = RESOLVERS[resolver];
  const resp = await fetch(r.url(name, type), { headers: r.headers });
  if (!resp.ok) throw new Error(`DoH HTTP ${resp.status}`);
  const data = await resp.json();
  const answers = data.Answer || [];
  return answers
    .filter((a) => a.type === TYPE_NUM[type])
    .map((a) => a.data.replace(/^"+|"+$/g, "").replace(/\.$/, ""));
}

// --- UI -----------------------------------------------------------------------

const $ = (id) => document.getElementById(id);
let CFG = null;

async function loadConfig() {
  const resp = await fetch("records.json");
  CFG = await resp.json();
  const sel = $("provider");
  for (const name of Object.keys(CFG.providers).sort()) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  }
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

async function runCheck(evt) {
  evt.preventDefault();
  const domain = $("domain").value.trim().replace(/\.$/, "");
  if (!domain) return;
  const provider = $("provider").value;
  const resolver = $("resolver").value;

  if (!HOSTNAME.test(domain)) {
    $("results").replaceChildren();
    $("fixes").replaceChildren();
    $("summary").textContent = `“${domain}” is not a valid domain name.`;
    return;
  }

  $("check").disabled = true;
  $("summary").textContent = `Checking ${domain}…`;
  $("results").replaceChildren();
  $("fixes").replaceChildren();

  let passed = 0;
  const failures = [];
  let currentGroup = null;
  let groupEl = null;

  try {
    for (const rec of CFG.records) {
      if (rec.type !== currentGroup) {
        currentGroup = rec.type;
        groupEl = el("div", "group");
        groupEl.appendChild(el("h2", null, CFG.group_headers[currentGroup]));
        $("results").appendChild(groupEl);
      }

      const ctx = resolveRecord(rec, domain);
      ctx.match = valueOf(ctx, CFG, "match");
      ctx.value = valueOf(ctx, CFG, "value");
      const expected = ctx.match;

      let actual = "";
      try {
        actual = (await query(resolver, ctx.qname, rec.type)).join(" / ");
      } catch (e) {
        actual = `(lookup error: ${e.message})`;
      }

      const ok = actual.toLowerCase().includes(expected.toLowerCase());
      const row = el("div", "row");
      row.appendChild(el("span", `badge ${ok ? "ok" : "fail"}`, ok ? "OK" : "FAIL"));
      row.appendChild(el("span", "rlabel", labelOf(rec)));
      if (ok) {
        row.appendChild(el("span", "rval", cap(actual)));
        passed++;
      } else {
        row.appendChild(el("span", "rval miss",
          `expected: ${expected}  —  got: ${cap(actual) || "(nothing)"}`));
        failures.push(ctx);
      }
      groupEl.appendChild(row);
    }

    $("summary").textContent =
      `Result: ${passed} passed, ${failures.length} failed.`;

    if (failures.length && provider) {
      $("fixes").appendChild(
        el("h2", null, `How to fix ${failures.length} record(s) in ${provider}:`));
      if ($("fixformat").value === "long") {
        for (const ctx of failures) {
          const card = el("div", "fix");
          card.appendChild(el("h3", null, `${ctx.type} ${ctx.label ?? ctx.host}`));
          card.appendChild(el("pre", null, renderFix(CFG, provider, ctx).join("\n")));
          $("fixes").appendChild(card);
        }
      } else {
        const groups = new Map(); // group failures by record type, in order
        for (const ctx of failures) {
          if (!groups.has(ctx.type)) groups.set(ctx.type, []);
          groups.get(ctx.type).push(ctx);
        }
        for (const [rtype, ctxs] of groups) {
          $("fixes").appendChild(fixTable(CFG, provider, rtype, ctxs));
        }
      }
    } else if (failures.length) {
      $("fixes").appendChild(el("p", "note",
        'Pick a provider in "Show fixes for" and re-check to see exactly what to enter.'));
    }
  } finally {
    $("check").disabled = false;
  }
}

loadConfig().then(() => {
  $("form").addEventListener("submit", runCheck);
});
