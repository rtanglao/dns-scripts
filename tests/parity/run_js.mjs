// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

// Parity harness: load app.js (the browser twin of verify_thundermail_dns.py) in
// a sandbox and run the shared fixtures through its pure interpreter functions,
// so tests/test_parity.py can assert the JS and Python results are identical.
//
// app.js is a plain browser script, not a module — its only top-level side effect
// is a trailing `loadConfig().then(...)`. We stub `fetch` to stay pending forever,
// so that promise never resolves and its DOM-touching callback never fires; the
// function declarations we need (matches / interpolate / resolveRecord / valueOf)
// are left on the sandbox global, closures over the top-level consts intact.

import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");
const appSrc = fs.readFileSync(path.join(repoRoot, "app.js"), "utf8");

const noop = () => {};
const domNode = { addEventListener: noop, appendChild: noop, replaceChildren: noop };
const sandbox = {
  // fetch never settles → loadConfig() suspends → the DOM callback never runs.
  fetch: () => new Promise(noop),
  document: { getElementById: () => domNode, createElement: () => domNode },
  history: { replaceState: noop },
  location: { pathname: "/", search: "" },
  URLSearchParams,
  Promise,
  console,
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(appSrc, sandbox, { filename: "app.js" });

const { matches, interpolate, resolveRecord } = sandbox;
const valueOf = sandbox.valueOf; // own global prop shadows Object.prototype.valueOf

const { cfg, matchCases, resolveCases } = JSON.parse(fs.readFileSync(0, "utf8"));

const out = { match: [], resolve: [] };

for (const c of matchCases) {
  out.match.push(matches(c.expected, c.answers, c.mode));
}

for (const c of resolveCases) {
  const ctx = resolveRecord(c.record, c.domain);
  ctx.match = valueOf(ctx, cfg, "match");
  ctx.value = valueOf(ctx, cfg, "value");
  out.resolve.push({
    qname: ctx.qname,
    fqdn: ctx.fqdn,
    subhost: ctx.subhost,
    service: ctx.service,
    protocol: ctx.protocol,
    srvhost: ctx.srvhost,
    srvsubhost: ctx.srvsubhost,
    match: ctx.match,
    value: ctx.value,
  });
}

process.stdout.write(JSON.stringify(out));
