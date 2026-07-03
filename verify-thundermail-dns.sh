#!/usr/bin/env bash
#
# verify-thundermail-dns.sh — check that a domain's DNS records match the
# Thundermail setup (MX, SRV, SPF/MTA-STS/TLSRPT/DMARC TXT, and DKIM CNAMEs).
#
# Usage:
#   ./verify-thundermail-dns.sh <domain>
#   ./verify-thundermail-dns.sh glamrocnamecheap.com
#
# Exit status is 0 only if every expected record is present and correct.
# Requires: dig (bind-tools / dnsutils).

set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
  echo "usage: $0 <domain>" >&2
  exit 2
fi

# Use an explicit resolver so results aren't served from a stale local cache.
RESOLVER="${DNS_RESOLVER:-1.1.1.1}"
MAIL_TARGET="mail.thundermail.com"

pass=0
fail=0

# query <type> <name> -> prints answer(s), one per line, trailing dots trimmed
query() {
  dig +short "@${RESOLVER}" "$2" "$1" | sed 's/\.$//'
}

# check <label> <expected-substring> <actual...>
check() {
  local label="$1" expected="$2"; shift 2
  local actual="$*"
  if grep -qiF -- "$expected" <<<"$actual"; then
    printf '  \033[32mOK\033[0m   %-46s %s\n' "$label" "$actual"
    pass=$((pass + 1))
  else
    printf '  \033[31mFAIL\033[0m %-46s expected to contain: %s\n' "$label" "$expected"
    printf '       %-46s got: %s\n' "" "${actual:-<empty>}"
    fail=$((fail + 1))
  fi
}

echo "Verifying Thundermail DNS for ${DOMAIN} (resolver ${RESOLVER})"
echo

echo "MX:"
check "@" "10 ${MAIL_TARGET}" "$(query MX "$DOMAIN")"

echo "SRV:"
check "_jmap._tcp"       "0 1 443 ${MAIL_TARGET}" "$(query SRV "_jmap._tcp.${DOMAIN}")"
check "_caldavs._tcp"    "0 1 443 ${MAIL_TARGET}" "$(query SRV "_caldavs._tcp.${DOMAIN}")"
check "_carddavs._tcp"   "0 1 443 ${MAIL_TARGET}" "$(query SRV "_carddavs._tcp.${DOMAIN}")"
check "_imaps._tcp"      "0 1 993 ${MAIL_TARGET}" "$(query SRV "_imaps._tcp.${DOMAIN}")"
check "_submission._tcp" "0 1 587 ${MAIL_TARGET}" "$(query SRV "_submission._tcp.${DOMAIN}")"

echo "TXT:"
check "@ (SPF)"        "v=spf1 include:spf.thundermail.com -all" "$(query TXT "$DOMAIN")"
check "_mta-sts"       "v=STSv1;"                                "$(query TXT "_mta-sts.${DOMAIN}")"
check "_smtp._tls"     "v=TLSRPTv1;"                             "$(query TXT "_smtp._tls.${DOMAIN}")"
check "_dmarc"         "v=DMARC1;"                               "$(query TXT "_dmarc.${DOMAIN}")"

echo "CNAME (DKIM):"
check "tm1._domainkey" "tm1.${DOMAIN}.dkim.thunderhosted.com" "$(query CNAME "tm1._domainkey.${DOMAIN}")"
check "tm2._domainkey" "tm2.${DOMAIN}.dkim.thunderhosted.com" "$(query CNAME "tm2._domainkey.${DOMAIN}")"
check "tm3._domainkey" "tm3.${DOMAIN}.dkim.thunderhosted.com" "$(query CNAME "tm3._domainkey.${DOMAIN}")"

echo
echo "Result: ${pass} passed, ${fail} failed."
[[ "$fail" -eq 0 ]]
